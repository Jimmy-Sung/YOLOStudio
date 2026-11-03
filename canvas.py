"""Native Qt image and bounding-box editor; no embedded browser."""
import copy
from PySide6.QtCore import QPointF,QRectF,QSize,Qt,Signal
from PySide6.QtGui import QBrush,QColor,QIcon,QImageReader,QPainter,QPen,QPixmap
from PySide6.QtWidgets import QWidget

COLORS=['#099d83','#e7a02b','#627ee7','#d76b92','#3d9bc7','#a27acc','#dc7557','#73a343']
HANDLE=5          # half size of a drawn handle, in screen pixels
GRAB=8            # tolerance for grabbing an edge or handle, in screen pixels
MIN_SIZE=.002     # smallest box, relative to the image
CURSORS={'l':Qt.CursorShape.SizeHorCursor,'r':Qt.CursorShape.SizeHorCursor,'t':Qt.CursorShape.SizeVerCursor,'b':Qt.CursorShape.SizeVerCursor,
         'lt':Qt.CursorShape.SizeFDiagCursor,'rb':Qt.CursorShape.SizeFDiagCursor,'rt':Qt.CursorShape.SizeBDiagCursor,'lb':Qt.CursorShape.SizeBDiagCursor}


def thumbnail(path,width,height):
    """Decode a reduced image directly (JPEG DCT scaling) instead of loading full size."""
    reader=QImageReader(str(path));reader.setAutoTransform(True);size=reader.size()
    if size.isValid() and size.width()>0 and size.height()>0:
        scale=min(width/size.width(),height/size.height(),1.0)
        reader.setScaledSize(QSize(max(1,round(size.width()*scale)),max(1,round(size.height()*scale))))
    image=reader.read()
    return QIcon(QPixmap.fromImage(image)) if not image.isNull() else QIcon()


class AnnotationCanvas(QWidget):
    edited=Signal()
    selection_changed=Signal(int)
    files_dropped=Signal(list)
    need_classes=Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setMinimumSize(300,280)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.pixmap=QPixmap()
        self.boxes,self.proposals,self.classes=[],[],[]
        self.selected,self.class_id=-1,0
        self.mode='draw'
        self.history=[]
        self.gesture=None
        self.handled=False
        self.empty_text=''
        self.zoom=1.0
        self.pan_offset=QPointF(0.0,0.0)
        self.setMouseTracking(True)
        # A tiled 16 px texture replaces thousands of drawPoint calls per frame.
        dot=QPixmap(16,16);dot.fill(QColor('#e9eef0'));painter=QPainter(dot);painter.setPen(QColor('#d1dbdf'));painter.drawPoint(8,8);painter.end()
        self.background=QBrush(dot)

    def load(self,path,boxes,proposals,classes):
        self.pixmap=QPixmap(str(path)) if path else QPixmap()
        self.boxes,self.proposals=copy.deepcopy(boxes),copy.deepcopy(proposals)
        self.classes,self.selected,self.history,self.handled=classes,-1,[],False
        self.gesture=None
        self.zoom=1.0
        self.pan_offset=QPointF(0.0,0.0)
        self.update()

    def reset_view(self):
        self.zoom=1.0
        self.pan_offset=QPointF(0.0,0.0)
        self.update()

    def image_rect(self):
        if self.pixmap.isNull():return QRectF()
        base_scale=min((self.width()-40)/self.pixmap.width(),(self.height()-40)/self.pixmap.height())
        scale=base_scale*self.zoom
        w,h=self.pixmap.width()*scale,self.pixmap.height()*scale
        cx,cy=self.width()/2+self.pan_offset.x(),self.height()/2+self.pan_offset.y()
        return QRectF(cx-w/2,cy-h/2,w,h)

    def box_rect(self,b):
        r=self.image_rect()
        return QRectF(r.x()+b['x']*r.width(),r.y()+b['y']*r.height(),b['w']*r.width(),b['h']*r.height())

    def position(self,p):
        r=self.image_rect()
        if r.width()<=0 or r.height()<=0:return QPointF(0,0)
        return QPointF(max(0,min(1,(p.x()-r.x())/r.width())),max(0,min(1,(p.y()-r.y())/r.height())))

    # ---- hit testing -------------------------------------------------
    @staticmethod
    def handle_points(rect):
        cx,cy=rect.center().x(),rect.center().y()
        return {'lt':QPointF(rect.left(),rect.top()),'t':QPointF(cx,rect.top()),'rt':QPointF(rect.right(),rect.top()),'r':QPointF(rect.right(),cy),
                'rb':QPointF(rect.right(),rect.bottom()),'b':QPointF(cx,rect.bottom()),'lb':QPointF(rect.left(),rect.bottom()),'l':QPointF(rect.left(),cy)}

    def edge_at(self,index,pos):
        """Return the handle/edge of box `index` under `pos` ('l','rb', ...) or None."""
        rect=self.box_rect(self.boxes[index])
        for name,point in self.handle_points(rect).items():
            if abs(point.x()-pos.x())<=GRAB and abs(point.y()-pos.y())<=GRAB:return name
        inside_x=rect.left()-GRAB<=pos.x()<=rect.right()+GRAB;inside_y=rect.top()-GRAB<=pos.y()<=rect.bottom()+GRAB
        edge=''
        if inside_y and abs(pos.x()-rect.left())<=GRAB:edge+='l'
        elif inside_y and abs(pos.x()-rect.right())<=GRAB:edge+='r'
        if inside_x and abs(pos.y()-rect.top())<=GRAB:edge+='t'
        elif inside_x and abs(pos.y()-rect.bottom())<=GRAB:edge+='b'
        return edge or None

    def hit(self,pos):
        """Find (index, edge) for resizing; the selected box wins, then the topmost box."""
        order=([self.selected] if 0<=self.selected<len(self.boxes) else [])+[i for i in range(len(self.boxes)-1,-1,-1) if i!=self.selected]
        for i in order:
            edge=self.edge_at(i,pos)
            if edge:return i,edge
        return -1,None

    def box_under(self,pos):
        if 0<=self.selected<len(self.boxes) and self.box_rect(self.boxes[self.selected]).contains(pos):return self.selected
        return next((i for i in range(len(self.boxes)-1,-1,-1) if self.box_rect(self.boxes[i]).contains(pos)),-1)

    # ---- editing -----------------------------------------------------
    def remember(self):
        self.history.append((copy.deepcopy(self.boxes),copy.deepcopy(self.proposals),self.handled))
        self.history=self.history[-50:]

    def undo(self):
        if self.history:
            self.boxes,self.proposals,self.handled=self.history.pop()
            self.selected=-1
            self.edited.emit()
            self.update()

    def delete_selected(self):
        if 0<=self.selected<len(self.boxes):
            self.remember()
            self.boxes.pop(self.selected)
            self.selected=-1
            self.edited.emit()
            self.update()

    def change_class(self,class_id):
        if 0<=self.selected<len(self.boxes):
            self.remember()
            self.boxes[self.selected]['class_id']=class_id
            self.edited.emit()
            self.update()

    def nudge(self,dx,dy,resize=False):
        """Keyboard fine adjustment of the selected box by one screen pixel."""
        if not 0<=self.selected<len(self.boxes) or self.pixmap.isNull():return False
        r=self.image_rect();b=self.boxes[self.selected];self.remember()
        ux,uy=dx/r.width(),dy/r.height()
        if resize:
            b['w']=max(MIN_SIZE,min(1-b['x'],b['w']+ux));b['h']=max(MIN_SIZE,min(1-b['y'],b['h']+uy))
        else:
            b['x']=max(0,min(1-b['w'],b['x']+ux));b['y']=max(0,min(1-b['h'],b['y']+uy))
        self.edited.emit();self.update();return True

    def accept(self):
        self.remember()
        for candidate in self.proposals:
            b={k:v for k,v in candidate.items() if k!='confidence'}
            if not any(old['class_id']==b['class_id'] and all(abs(old[k]-b[k])<1e-5 for k in ('x','y','w','h')) for old in self.boxes):self.boxes.append(b)
        self.proposals=[]
        self.handled=True
        self.edited.emit()
        self.update()

    # ---- painting ----------------------------------------------------
    def paintEvent(self,event):
        p=QPainter(self)
        p.fillRect(self.rect(),self.background)
        r=self.image_rect()
        if self.pixmap.isNull():
            p.setPen(QColor('#78968e'))
            p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,self.empty_text)
            return
        p.drawPixmap(r,self.pixmap,QRectF(self.pixmap.rect()))
        metrics=p.fontMetrics()
        def paint_box(b,candidate=False,index=-1):
            rect=self.box_rect(b)
            color=QColor(COLORS[b['class_id']%len(COLORS)])
            pen=QPen(color,2.5 if index==self.selected else 1.8)
            if candidate:pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawRect(rect)
            fill=QColor(color);fill.setAlpha(40 if index==self.selected else 22);p.fillRect(rect,fill)
            name=self.classes[b['class_id']] if 0<=b['class_id']<len(self.classes) else str(b['class_id'])
            label=name+(f" {b.get('confidence',0):.0%}" if candidate else '')
            tr=QRectF(rect.x(),max(r.top(),rect.y()-21),metrics.horizontalAdvance(label)+12,21)
            p.fillRect(tr,color);p.setPen(Qt.GlobalColor.white)
            p.drawText(tr.adjusted(6,0,0,0),Qt.AlignmentFlag.AlignVCenter,label)
            if index==self.selected:
                p.setPen(QPen(color,1.5))
                for point in self.handle_points(rect).values():
                    handle=QRectF(point.x()-HANDLE,point.y()-HANDLE,HANDLE*2,HANDLE*2)
                    p.fillRect(handle,Qt.GlobalColor.white);p.drawRect(handle)
        for b in self.proposals:paint_box(b,True)
        for i,b in enumerate(self.boxes):
            if i!=self.selected:paint_box(b,False,i)
        if 0<=self.selected<len(self.boxes):paint_box(self.boxes[self.selected],False,self.selected)
        if self.gesture and self.gesture['type']=='draw':
            a,b=self.gesture['start'],self.gesture['last']
            paint_box({'class_id':self.class_id,'x':min(a.x(),b.x()),'y':min(a.y(),b.y()),'w':abs(a.x()-b.x()),'h':abs(a.y()-b.y())})

    # ---- mouse & wheel -----------------------------------------------
    def wheelEvent(self,event):
        if self.pixmap.isNull():
            super().wheelEvent(event);return
        delta=event.angleDelta().y()
        if not delta:return
        factor=1.15 if delta>0 else 1/1.15
        old_zoom=self.zoom
        new_zoom=max(0.5,min(15.0,old_zoom*factor))
        if abs(new_zoom-old_zoom)<1e-4:return
        pos=event.position()
        cx=self.width()/2+self.pan_offset.x()
        cy=self.height()/2+self.pan_offset.y()
        ratio=new_zoom/old_zoom
        new_cx=pos.x()-(pos.x()-cx)*ratio
        new_cy=pos.y()-(pos.y()-cy)*ratio
        self.pan_offset=QPointF(new_cx-self.width()/2,new_cy-self.height()/2)
        self.zoom=new_zoom
        self.update_cursor(pos)
        self.update()

    def mousePressEvent(self,event):
        if self.pixmap.isNull():return
        pos=event.position();self.setFocus()
        if event.button()==Qt.MouseButton.MiddleButton:
            self.gesture={'type':'pan','last_pos':pos}
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button()!=Qt.MouseButton.LeftButton:return

        is_alt=bool(event.modifiers()&Qt.KeyboardModifier.AltModifier)
        is_edit_mode=is_alt or (self.mode=='select')

        index,edge=self.hit(pos)
        if index>=0 and (is_edit_mode or index==self.selected):
            self.selected=index;b=self.boxes[index]
            self.gesture={'type':'resize','edge':edge,'start':self.position(pos),'original':copy.deepcopy(b),'snapshot':copy.deepcopy(self.boxes)}
            self.selection_changed.emit(self.selected);self.update();return

        if not self.image_rect().contains(pos):
            if is_edit_mode:
                self.gesture={'type':'pan','last_pos':pos}
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return
            if self.selected>=0:self.selected=-1;self.selection_changed.emit(-1);self.update()
            return

        p=self.position(pos)
        under=self.box_under(pos)

        if is_edit_mode:
            self.selected=under
            if under>=0:
                self.gesture={'type':'move','start':p,'original':copy.deepcopy(self.boxes[under]),'snapshot':copy.deepcopy(self.boxes)}
            else:
                self.gesture={'type':'pan','last_pos':pos}
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.selection_changed.emit(self.selected);self.update();return

        if under>=0 and under==self.selected:
            self.gesture={'type':'move','start':p,'original':copy.deepcopy(self.boxes[under]),'snapshot':copy.deepcopy(self.boxes)}
            self.selection_changed.emit(self.selected);self.update();return

        if not self.classes:
            self.need_classes.emit();return
        self.selected=-1;self.gesture={'type':'draw','start':p,'last':p,'origin':pos}
        self.selection_changed.emit(self.selected);self.update()

    def update_cursor(self,pos):
        if self.pixmap.isNull():self.unsetCursor();return
        is_alt=bool(self.get_modifiers()&Qt.KeyboardModifier.AltModifier)
        is_edit=is_alt or (self.mode=='select')
        _,edge=self.hit(pos)
        if edge and (is_edit or _==self.selected):self.setCursor(CURSORS[edge]);return
        under=self.box_under(pos)
        if under>=0 and (is_edit or under==self.selected):self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif not is_edit and self.mode=='draw' and self.image_rect().contains(pos):self.setCursor(Qt.CursorShape.CrossCursor)
        elif is_edit:self.setCursor(Qt.CursorShape.OpenHandCursor if not self.image_rect().contains(pos) or under<0 else Qt.CursorShape.ArrowCursor)
        else:self.setCursor(Qt.CursorShape.ArrowCursor)

    def get_modifiers(self):
        from PySide6.QtWidgets import QApplication
        return QApplication.keyboardModifiers()

    def mouseMoveEvent(self,event):
        if not self.gesture:
            self.update_cursor(event.position());return
        pos=event.position();p=self.position(pos);g=self.gesture
        if g['type']=='pan':
            delta=pos-g['last_pos']
            g['last_pos']=pos
            self.pan_offset+=QPointF(delta.x(),delta.y())
            self.update();return
        if g['type']=='draw':
            g['last']=p
        elif g['type']=='move':
            o,b=g['original'],self.boxes[self.selected]
            b['x']=max(0,min(1-o['w'],o['x']+p.x()-g['start'].x()));b['y']=max(0,min(1-o['h'],o['y']+p.y()-g['start'].y()))
        elif g['type']=='resize':
            o,b,edge=g['original'],self.boxes[self.selected],g['edge']
            dx,dy=p.x()-g['start'].x(),p.y()-g['start'].y()
            x1,y1,x2,y2=o['x'],o['y'],o['x']+o['w'],o['y']+o['h']
            if 'l' in edge:x1=max(0,min(1,x1+dx))
            if 'r' in edge:x2=max(0,min(1,x2+dx))
            if 't' in edge:y1=max(0,min(1,y1+dy))
            if 'b' in edge:y2=max(0,min(1,y2+dy))
            x1,x2=min(x1,x2),max(x1,x2);y1,y2=min(y1,y2),max(y1,y2)
            if x2-x1<MIN_SIZE:
                if 'l' in edge:x1=max(0,x2-MIN_SIZE)
                else:x2=min(1,x1+MIN_SIZE)
            if y2-y1<MIN_SIZE:
                if 't' in edge:y1=max(0,y2-MIN_SIZE)
                else:y2=min(1,y1+MIN_SIZE)
            b['x'],b['y'],b['w'],b['h']=x1,y1,x2-x1,y2-y1
        self.update()

    def mouseReleaseEvent(self,event):
        if not self.gesture:return
        g,self.gesture=self.gesture,None
        if g['type']=='pan':
            self.update_cursor(event.position());return
        if g['type']=='draw':
            a,b=g['start'],g['last'];w,h=abs(a.x()-b.x()),abs(a.y()-b.y());r=self.image_rect()
            if w*r.width()>=4 and h*r.height()>=4:
                self.remember();self.boxes.append({'class_id':self.class_id,'x':min(a.x(),b.x()),'y':min(a.y(),b.y()),'w':w,'h':h});self.selected=len(self.boxes)-1;self.edited.emit()
            else:
                self.selected=self.box_under(g['origin'])
        elif g['snapshot']!=self.boxes:
            self.history.append((g['snapshot'],copy.deepcopy(self.proposals),self.handled));self.history=self.history[-50:];self.edited.emit()
        self.selection_changed.emit(self.selected);self.update_cursor(event.position());self.update()

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and 0<=self.selected<len(self.boxes):
            self.delete_selected();return
        if event.key()==Qt.Key.Key_Alt:
            self.update_cursor(self.mapFromGlobal(self.cursor().pos()))
        steps={Qt.Key.Key_Up:(0,-1),Qt.Key.Key_Down:(0,1),Qt.Key.Key_Left:(-1,0),Qt.Key.Key_Right:(1,0)}
        modifiers=event.modifiers()
        if event.key() in steps and 0<=self.selected<len(self.boxes) and modifiers&(Qt.KeyboardModifier.AltModifier|Qt.KeyboardModifier.ShiftModifier):
            dx,dy=steps[event.key()];factor=10 if modifiers&Qt.KeyboardModifier.ControlModifier else 1
            self.nudge(dx*factor,dy*factor,resize=bool(modifiers&Qt.KeyboardModifier.ShiftModifier));return
        if event.key()==Qt.Key.Key_Escape and self.selected>=0:
            self.selected=-1;self.selection_changed.emit(-1);self.update();return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key.Key_Alt:
            self.update_cursor(self.mapFromGlobal(self.cursor().pos()))
        super().keyReleaseEvent(event)

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()

    def dropEvent(self,event):
        self.files_dropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]);event.acceptProposedAction()
