import { useState, useEffect } from 'react';
import { Bell, X, Check, Clock, Trophy } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSocket } from '../hooks/useWebSocket';

export const NotificationCenter = ({ userId }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const { socket } = useWebSocket(userId);

  useEffect(() => {
    if (!socket) return;

    const handleNotification = (data) => {
      setNotifications(prev => [{
        id: Date.now(),
        ...data,
        read: false
      }, ...prev]);
    };

    socket.on('notification', handleNotification);
    socket.on('task:completed', handleNotification);
    socket.on('achievement', handleNotification);

    return () => {
      socket.off('notification', handleNotification);
      socket.off('task:completed', handleNotification);
      socket.off('achievement', handleNotification);
    };
  }, [socket]);

  const markAsRead = (id) => {
    setNotifications(prev =>
      prev.map(n => n.id === id ? { ...n, read: true } : n)
    );
  };

  const clearAll = () => {
    setNotifications([]);
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="relative">
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg hover:bg-slate-100"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute top-1 right-1 w-4 h-4 bg-red-500 text-white text-xs flex items-center justify-center rounded-full"
          >
            {unreadCount}
          </motion.span>
        )}
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden z-50"
          >
            <div className="p-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white flex justify-between items-center">
              <h3 className="font-semibold">Notifications</h3>
              {notifications.length > 0 && (
                <button onClick={clearAll} className="text-sm hover:underline">
                  Clear all
                </button>
              )}
            </div>

            <div className="max-h-96 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-8 text-center text-slate-500">
                  <Bell size={32} className="mx-auto mb-2 opacity-50" />
                  <p>No notifications</p>
                </div>
              ) : (
                notifications.map((notif) => (
                  <motion.div
                    key={notif.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    className={`p-3 border-b border-slate-100 hover:bg-slate-50 cursor-pointer ${
                      !notif.read ? 'bg-violet-50' : ''
                    }`}
                    onClick={() => markAsRead(notif.id)}
                  >
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <p className="text-sm font-medium">{notif.title}</p>
                        <p className="text-xs text-slate-500">{notif.message}</p>
                        <p className="text-xs text-slate-400 mt-1">
                          {new Date(notif.timestamp).toLocaleTimeString()}
                        </p>
                      </div>
                      {notif.icon && (
                        <span className="text-xl">{notif.icon}</span>
                      )}
                    </div>
                  </motion.div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
