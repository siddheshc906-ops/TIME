// frontend/src/components/AnimatedTask.jsx
import { motion } from "framer-motion";
import { Edit2, Trash2, Check, X } from "lucide-react";

export const AnimatedTask = ({
  task,
  onComplete,
  onDelete,
  onEdit,
  onSave,
  onCancel,
  isEditing,
  editText,
  setEditText,
  getPriorityColor
}) => {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -100 }}
      whileHover={{ 
        scale: 1.02,
        boxShadow: "0 10px 25px -5px rgba(0,0,0,0.1)"
      }}
      className={`bg-white/80 backdrop-blur p-4 rounded-xl border shadow-sm ${getPriorityColor(task.priority)}`}
    >
      <div className="flex gap-4 items-start">
        {/* Complete Button */}
        <motion.button
          whileHover={{ scale: 1.2 }}
          whileTap={{ scale: 0.9 }}
          onClick={() => onComplete(task._id, task.completed)}
          className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition ${
            task.completed
              ? "bg-violet-600 border-violet-600 hover:bg-violet-700"
              : "border-slate-300 hover:border-violet-500"
          }`}
        >
          {task.completed && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 300 }}
            >
              <Check className="text-white" size={16} />
            </motion.div>
          )}
        </motion.button>

        {/* Task Content */}
        <div className="flex-1">
          {isEditing ? (
            <motion.input
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="border px-3 py-2 rounded-lg w-full bg-white focus:ring-2 focus:ring-violet-500"
              onKeyPress={(e) => e.key === "Enter" && onSave(task._id)}
              autoFocus
            />
          ) : (
            <motion.p
              animate={task.completed ? { opacity: 0.7 } : { opacity: 1 }}
              className={task.completed ? "line-through" : ""}
            >
              {task.text}
            </motion.p>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <motion.button
                whileHover={{ scale: 1.2 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => onSave(task._id)}
                className="text-green-600 hover:text-green-800"
              >
                <Check size={18} />
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.2 }}
                whileTap={{ scale: 0.9 }}
                onClick={onCancel}
                className="text-red-600 hover:text-red-800"
              >
                <X size={18} />
              </motion.button>
            </>
          ) : (
            <>
              <motion.button
                whileHover={{ scale: 1.2 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => onEdit(task)}
                className="text-slate-600 hover:text-violet-600"
              >
                <Edit2 size={18} />
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.2 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => onDelete(task._id)}
                className="text-slate-600 hover:text-red-600"
              >
                <Trash2 size={18} />
              </motion.button>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
};