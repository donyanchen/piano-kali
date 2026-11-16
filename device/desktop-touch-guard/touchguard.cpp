// SPDX-License-Identifier: GPL-3.0-or-later
// Native KWin 6.7.4 desktop-only input integration. No evdev reads or grabs.
#include <effect/effect.h>
#include <effect/offscreenquickview.h>
#include <effect/effecthandler.h>
#include <input.h>
#include <input_event.h>
#include <workspace.h>
#include <window.h>
#include <wayland_server.h>
#include <wayland/seat.h>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QHash>
#include <QPointer>
#include <QTimer>
#include <cmath>

namespace KWin {
class DesktopTouchGuard final : public Effect {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.sheng.DesktopTouch")
    class Filter final : public InputEventFilter {
    public:
        explicit Filter(DesktopTouchGuard *owner):InputEventFilter(InputFilterOrder::ScreenEdge),m_owner(owner){}
        bool pointerButton(PointerButtonEvent *e)override{if(e->state==PointerButtonState::Pressed)m_owner->dockPress(input()->findToplevel(e->position));return false;}
        bool touchDown(TouchDownEvent *e)override{return m_owner->down(e);}
        bool touchMotion(TouchMotionEvent *e)override{return m_owner->motion(e);}
        bool touchUp(TouchUpEvent *e)override{return m_owner->up(e);}
        bool touchCancel()override{m_owner->clear();return false;}
    private:DesktopTouchGuard *m_owner;
    };
public:
    DesktopTouchGuard()
    {
        m_filter=std::make_unique<Filter>(this);input()->installInputEventFilter(m_filter.get());
        QDBusConnection::sessionBus().registerService("org.sheng.DesktopTouch");
        QDBusConnection::sessionBus().registerObject("/org/sheng/DesktopTouch",this,QDBusConnection::ExportAllSlots);
        QDBusConnection::sessionBus().connect("org.sheng.DesktopPolicy","/org/sheng/DesktopPolicy","org.sheng.DesktopPolicy","PointerPresenceChanged",this,SLOT(pointerPresence(bool)));
        QDBusConnection::sessionBus().connect("org.sheng.DesktopPolicy","/org/sheng/DesktopPolicy","org.sheng.DesktopPolicy","DockVisibilityChanged",this,SLOT(dockVisibility(bool)));
        m_hintTimer.setSingleShot(true);
        connect(&m_hintTimer,&QTimer::timeout,this,[this]{m_hint.reset();m_hintOutput=nullptr;});
        connect(effects,&EffectsHandler::screenLockingChanged,this,[this](bool locked){if(locked){m_hintTimer.stop();m_hint.reset();m_hintOutput=nullptr;clear();clearRevealConstraint();}});
        auto *watch=new QDBusServiceWatcher("org.sheng.DesktopPolicy",QDBusConnection::sessionBus(),QDBusServiceWatcher::WatchForOwnerChange,this);
        connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this]{readPresence();});
        QTimer::singleShot(0,this,&DesktopTouchGuard::readPresence);
        connect(workspace(),&Workspace::windowAdded,this,[this](Window *){syncDrawerDock();});
        connect(workspace(),&Workspace::windowRemoved,this,[this](Window *){syncDrawerDock();});
        connect(workspace(),&Workspace::showingDesktopChanged,this,[this](bool showing,bool){if(showing)clearRevealConstraint();});
        QTimer::singleShot(0,this,&DesktopTouchGuard::syncDrawerDock);
    }
    ~DesktopTouchGuard()override{clearRevealConstraint();clearDrawerDock();m_hint.reset();m_filter.reset();QDBusConnection::sessionBus().unregisterObject("/org/sheng/DesktopTouch");QDBusConnection::sessionBus().unregisterService("org.sheng.DesktopTouch");}
    bool isActive()const override{return m_hint!=nullptr;}
    bool down(TouchDownEvent *event)
    {
        if(m_contacts.contains(event->id))clear();
        auto *window=input()->findToplevel(event->pos);
        const bool desktop=window&&window->isDesktop();
        m_contacts.insert(event->id,desktop);
        if(m_contacts.size()>1)m_multi=true;
        auto *output=workspace()->outputAt(event->pos);
        const bool homeEdge=m_revealDock&&!m_dockHidden&&!m_dismissPending&&m_revealDock->output()==output;
        if(m_contacts.size()==1&&(m_dockHidden||homeEdge)&&output&&!waylandServer()->isScreenLocked()
            &&event->pos.y()>=output->geometry().bottom()-9&&bottomDock(output)){
            m_edgeId=event->id;m_edgeOrigin=m_edgeLast=event->pos;m_edgeOutput=output;m_multi=false;
            m_edgeHome=homeEdge;
            m_edgeSecond=m_hint&&m_hintTimer.isActive()&&m_hintOutput==output;
            ++m_edgePresses;
            return true; // The same bottom edge advances hint -> Dock -> desktop.
        }
        dockPress(window);
        if(window&&window->isDock()&&!waylandServer()->isScreenLocked()&&m_revealDock==window&&!m_dismissPending)dispatch("RevealDock");
        if(m_contacts.size()==1&&desktop&&!waylandServer()->isScreenLocked()){
            m_id=event->id;m_window=window;m_origin=m_last=event->pos;m_cancelled=false;m_multi=false;++m_presses;
        }
        return false; // Native desktop taps and long-press menus still receive down/up.
    }
    bool motion(TouchMotionEvent *event)
    {
        if(event->id==m_edgeId){m_edgeLast=event->pos;return true;}
        if(!m_contacts.value(event->id,false)||waylandServer()->isScreenLocked())return false;
        if(event->id!=m_id)return true;
        m_last=event->pos;
        const auto delta=m_last-m_origin;
        if(!m_cancelled&&!m_multi&&std::hypot(delta.x(),delta.y())>=3){
            // The desktop receives a real touch cancellation before any motion,
            // so its synthesized mouse path can never create a rubber band.
            waylandServer()->seat()->notifyTouchCancel();
            waylandServer()->seat()->notifyTouchFrame();
            m_cancelled=true;++m_cancelCount;
        }
        return true; // Only motion belonging to a desktop surface is suppressed.
    }
    bool up(TouchUpEvent *event)
    {
        m_contacts.remove(event->id);
        if(event->id==m_edgeId){
            const auto delta=m_edgeLast-m_edgeOrigin;
            if(!m_multi&&m_edgeOutput&&!waylandServer()->isScreenLocked()
                &&delta.y()<-36&&-delta.y()>std::abs(delta.x())*1.25){
                if(m_edgeHome){
                    if(m_revealDock&&!m_dockHidden&&!m_dismissPending){++m_homeGestures;m_dismissPending=true;dispatch("ShowDesktop");}
                }else if(m_dockHidden&&m_edgeSecond&&m_hint&&m_hintTimer.isActive()){
                    m_hintTimer.stop();m_hint.reset();m_hintOutput=nullptr;
                    clearRevealConstraint();m_revealBelow=workspace()->activeWindow();m_revealDock=bottomDock(m_edgeOutput);
                    if(m_revealBelow&&m_revealDock)workspace()->constrain(m_revealBelow,m_revealDock);
                    ++m_reveals;dispatch("RevealDock");
                }else if(m_dockHidden)showDockHint(m_edgeOutput);
            }
            m_edgeId=-1;m_edgeOutput=nullptr;
            if(m_contacts.isEmpty())m_multi=false;
            return true; // No downstream filter saw this sequence's down.
        }
        if(event->id==m_id){
            const auto delta=m_last-m_origin;
            if(m_cancelled&&!m_multi&&!waylandServer()->isScreenLocked()){
                QString method;
                if(delta.y()<-56&&-delta.y()>std::abs(delta.x())*1.25)method="OpenAppDrawer";
                else if(!m_pointer&&delta.y()>56&&delta.y()>std::abs(delta.x())*1.25){auto *out=workspace()->outputAt(m_origin);if(out&&m_origin.x()>out->geometry().center().x())method="OpenControlCenter";}
                if(!method.isEmpty()){++m_actions;QTimer::singleShot(0,this,[this,method]{dispatch(method);});}
            }
            m_id=-1;m_window=nullptr;
        }
        if(m_contacts.isEmpty())m_multi=false;
        // The lower KWin filters must see up even after the Wayland cancel, so
        // screen-edge and multi-finger trackers can clean up their own IDs.
        return false;
    }
    void clear(){m_contacts.clear();m_id=m_edgeId=-1;m_edgeOutput=nullptr;m_window=nullptr;m_cancelled=false;m_multi=false;}
    void dockPress(Window *window)
    {
        if(!m_revealDock||!window||m_dismissPending||waylandServer()->isScreenLocked())return;
        // Native Dock menus/popups and its fullscreen app drawer belong to the
        // Dock interaction. A click in the already-focused app also dismisses.
        int depth=0;
        for(auto *owner=window;owner&&depth++<16;owner=owner->transientFor()){
            if(owner==m_revealDock||owner==m_drawer)return;
        }
        m_dismissPending=true;++m_dismissals;
        dispatch("DismissDock"); // Observe only: never consume the application's press.
    }
public slots:
    void pointerPresence(bool present){m_pointer=present;}
    void dockVisibility(bool hidden){m_dockHidden=hidden;if(hidden)clearRevealConstraint();else{m_hintTimer.stop();m_hint.reset();m_hintOutput=nullptr;}}
    QString GetStatus()const{return QString::fromUtf8(QJsonDocument(QJsonObject{{"scope","desktop-and-bottom-edge"},{"desktopPresses",m_presses},{"cancelledDrags",m_cancelCount},{"actions",m_actions},{"trackedPoints",m_contacts.size()},{"pointerPresent",m_pointer},{"drawerDockLinked",!m_drawer.isNull()&&!m_dock.isNull()},{"dockHidden",m_dockHidden},{"dockHintVisible",m_hint!=nullptr},{"bottomEdgePresses",m_edgePresses},{"dockReveals",m_reveals},{"dockOutsideDismissals",m_dismissals},{"dockHomeGestures",m_homeGestures}}).toJson(QJsonDocument::Compact));}
private:
    std::unique_ptr<OffscreenQuickScene> m_hint;
    QTimer m_hintTimer;
    QPointer<LogicalOutput> m_hintOutput,m_edgeOutput;
    QPointer<Window> m_revealBelow,m_revealDock;
    QPointF m_edgeOrigin,m_edgeLast;
    int m_edgeId=-1,m_edgePresses=0,m_reveals=0,m_dismissals=0,m_homeGestures=0;
    bool m_dockHidden=false,m_edgeSecond=false,m_edgeHome=false,m_dismissPending=false;
    void clearRevealConstraint(){if(m_revealBelow&&m_revealDock)workspace()->unconstrain(m_revealBelow,m_revealDock);m_revealBelow=nullptr;m_revealDock=nullptr;m_dismissPending=false;}
    Window *bottomDock(LogicalOutput *output)const{
        for(auto *win:workspace()->windows())if(!win->isDeleted()&&win->isDock()&&win->resourceClass()==QByteArrayLiteral("plasmashell")
            &&win->output()==output&&win->frameGeometry().center().y()>output->geometry().center().y()
            &&win->frameGeometry().width()>win->frameGeometry().height())return win;
        return nullptr;
    }
    void showDockHint(LogicalOutput *output){
        auto *dock=bottomDock(output);if(!dock)return;
        m_hint=std::make_unique<OffscreenQuickScene>();m_hint->setSource(QUrl(QStringLiteral(SHENG_GUARD_HINT_URL)));
        if(!m_hint->rootItem()){m_hint.reset();return;}
        const auto screen=output->geometry();
        // The installed floating host adds 12px each side around the actual Dock.
        const int width=std::max(48,int(dock->frameGeometry().width())-24);
        m_hint->setGeometry(QRect(int(dock->frameGeometry().center().x()-width/2),int(screen.bottom())-8,width,8));
        m_hintOutput=output;m_hintTimer.start(3000);
    }
    QPointer<Window> m_drawer,m_dock;
    void clearDrawerDock(){if(m_drawer&&m_dock)workspace()->unconstrain(m_drawer,m_dock);m_drawer=nullptr;m_dock=nullptr;}
    void syncDrawerDock()
    {
        Window *drawer=nullptr,*dock=nullptr;
        for(auto *win:workspace()->windows()){
            if(!win->isDeleted()&&win->caption()==QStringLiteral("Sheng Application Drawer")&&win->resourceClass()==QByteArrayLiteral("org.kde.plasmashell")){
                drawer=win;break;
            }
        }
        if(drawer&&drawer->output()){
            const auto area=drawer->output()->geometry();
            for(auto *win:workspace()->windows()){
                if(!win->isDeleted()&&win->isDock()&&win->resourceClass()==QByteArrayLiteral("plasmashell")&&win->output()==drawer->output()
                    &&win->frameGeometry().center().y()>area.center().y()&&win->frameGeometry().width()>win->frameGeometry().height()){
                    dock=win;break;
                }
            }
        }
        if(drawer==m_drawer&&dock==m_dock)return;
        clearDrawerDock();
        if(drawer&&dock){m_drawer=drawer;m_dock=dock;workspace()->constrain(drawer,dock);}
    }
    std::unique_ptr<Filter> m_filter;
    QHash<int,bool> m_contacts;
    QPointer<Window> m_window;
    QPointF m_origin,m_last;
    int m_id=-1,m_presses=0,m_cancelCount=0,m_actions=0;
    bool m_pointer=true,m_cancelled=false,m_multi=false;
    void dispatch(const QString &method){auto message=QDBusMessage::createMethodCall("org.sheng.DesktopPolicy","/org/sheng/DesktopPolicy","org.sheng.DesktopPolicy",method);QDBusConnection::sessionBus().asyncCall(message);}
    void readPresence(){auto msg=QDBusMessage::createMethodCall("org.sheng.DesktopPolicy","/org/sheng/DesktopPolicy","org.sheng.DesktopPolicy","GetState");auto *w=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg),this);connect(w,&QDBusPendingCallWatcher::finished,this,[this](QDBusPendingCallWatcher *w){QDBusPendingReply<QString> reply=*w;if(!reply.isError()){const auto state=QJsonDocument::fromJson(reply.value().toUtf8()).object();m_pointer=state["pointer_present"].toBool(true);dockVisibility(state["dock_hidden"].toBool()&&!state["dock_revealed"].toBool()&&!state["showing_desktop"].toBool());}w->deleteLater();});}
};
KWIN_EFFECT_FACTORY_SUPPORTED(DesktopTouchGuard,"metadata.json",return waylandServer()!=nullptr;)
}
#include "touchguard.moc"
