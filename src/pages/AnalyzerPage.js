import { useState, useEffect } from "react";
import { Brain, Plus, Trash2, Bot, Send, Sparkles, Clock, Target, Zap } from "lucide-react";
import BackgroundLayout from "../components/BackgroundLayout";

export const AnalyzerPage = () => {
  const [tasks, setTasks] = useState([
    {
      id: Date.now(),
      name: "",
      priority: "medium",
      difficulty: "medium",
      time: "",
    },
  ]);

  const [optimizedTasks, setOptimizedTasks] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [actualTimes, setActualTimes] = useState({});
  const [planHistory, setPlanHistory] = useState([]);
  const [accuracy, setAccuracy] = useState(null);
  
  // AI Assistant states
  const [chatMessages, setChatMessages] = useState([
    { 
      id: 1, 
      type: 'ai', 
      message: "Hello! I'm your AI Coach. I can help you plan your day, answer productivity questions, and give personalized advice. How can I help you today?",
      suggestions: ["Plan my day", "Give me productivity advice", "Analyze my habits"]
    }
  ]);
  const [userInput, setUserInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  /* ---------------- Helpers ---------------- */

  const addRow = () => {
    setTasks(prev => [
      ...prev,
      {
        id: Date.now() + Math.random(),
        name: "",
        priority: "medium",
        difficulty: "medium",
        time: "",
      },
    ]);
  };

  const removeRow = (id) => {
    setTasks(prev => prev.filter(t => t.id !== id));
  };

  const updateTask = (id, field, value) => {
    setTasks(prev =>
      prev.map(t =>
        t.id === id ? { ...t, [field]: value } : t
      )
    );
  };

  const updateActualTime = (id, value) => {
    setActualTimes(prev => ({
      ...prev,
      [id]: parseFloat(value)
    }));
  };

  /* ---------------- AI ENGINE ---------------- */

  const analyzeDay = async () => {
    const selected = tasks
      .filter(t => t.name && t.time)
      .map(t => ({
        name: t.name,
        priority: t.priority,
        difficulty: t.difficulty,
        time: Math.max(0.5, parseFloat(t.time)),
      }));

    if (!selected.length) return;

    try {
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/analyze-day`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify({ tasks: selected }),
      });

      if (!res.ok) {
        console.error("Backend error:", res.status);
        return;
      }

      const data = await res.json();

      setOptimizedTasks(data.optimizedTasks || []);
      setSchedule(data.schedule || []);

      // Add AI message about the plan
      addAIMessage(`I've optimized your day! Here's your schedule based on priority and difficulty. You can adjust times and I'll learn from your feedback.`);

    } catch (err) {
      console.error("Fetch failed:", err);
      addAIMessage("Sorry, I couldn't optimize your day right now. Please try again.");
    }
  };

  // AI Assistant chat function
  const sendMessageToAI = async (message) => {
    setIsLoading(true);
    
    try {
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/ai-assistant/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify({ message }),
      });

      if (!res.ok) {
        throw new Error("Failed to get AI response");
      }

      const data = await res.json();
      
      if (data.type === 'ai_response') {
        addAIMessage(data.message);
      } else {
        addAIMessage("I'm having trouble understanding. Could you rephrase that?");
      }
    } catch (err) {
      console.error("AI chat error:", err);
      addAIMessage("Sorry, I'm having trouble connecting. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const addAIMessage = (message, suggestions = []) => {
    setChatMessages(prev => [...prev, { 
      id: Date.now(), 
      type: 'ai', 
      message,
      suggestions 
    }]);
  };

  const addUserMessage = (message) => {
    setChatMessages(prev => [...prev, { 
      id: Date.now(), 
      type: 'user', 
      message 
    }]);
  };

  const handleSendMessage = () => {
    if (!userInput.trim()) return;
    
    addUserMessage(userInput);
    sendMessageToAI(userInput);
    setUserInput("");
  };

  const handleQuickAction = (action) => {
    let message = "";
    switch(action) {
      case "Plan my day":
        message = "I need to plan my day. Can you help me organize my tasks?";
        break;
      case "Give me productivity advice":
        message = "Give me productivity advice for deep work and focus.";
        break;
      case "Analyze my habits":
        message = "Analyze my productivity habits and suggest improvements.";
        break;
      default:
        message = action;
    }
    
    addUserMessage(message);
    sendMessageToAI(message);
  };

  const saveFeedback = async (task) => {
    const actual = actualTimes[task.id];

    if (!actual) {
      alert("Please enter actual time first");
      return;
    }

    try {
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/task-feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify({
          name: task.name,
          difficulty: task.difficulty,
          priority: task.priority,
          aiTime: task.aiTime,
          actualTime: parseFloat(actual),
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to save feedback");
      }

      alert("Feedback saved ✅");
      addAIMessage(`Thanks for the feedback! I'll remember that for next time.`);

    } catch (err) {
      console.error(err);
      alert("Error saving feedback");
    }
  };
  
  const deletePlan = async (planId) => {
    try {
      await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/daily-plans/${planId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
      });

      setPlanHistory(prev => prev.filter(p => p._id !== planId));

    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/daily-plans`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
        });

        if (!res.ok) return;

        const data = await res.json();
        setPlanHistory(data);

      } catch (err) {
        console.error(err);
      }
    };

    fetchPlans();
  }, []);
  
  useEffect(() => {
    const fetchAccuracy = async () => {
      try {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/accuracy`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
        });

        if (!res.ok) return;

        const data = await res.json();
        setAccuracy(data);

      } catch (err) {
        console.error(err);
      }
    };

    fetchAccuracy();
  }, []);

  /* ---------------- UI ---------------- */

  return (
    <BackgroundLayout>
      <div className="py-12 px-6 max-w-7xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 bg-violet-600 rounded-xl flex items-center justify-center">
            <Brain className="text-white" />
          </div>
          <h1 className="text-4xl font-bold">Smart Daily Task Analyzer</h1>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left Column - Task Analyzer (2/3 width) */}
          <div className="lg:col-span-2 space-y-8">
            
            {/* Input Table */}
            <div className="bg-white/80 rounded-2xl border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-100">
                  <tr>
                    <th className="p-3 text-left">Task</th>
                    <th className="p-3">Priority</th>
                    <th className="p-3">Difficulty</th>
                    <th className="p-3">My Time</th>
                    <th></th>
                  </tr>
                </thead>

                <tbody>
                  {tasks.map(task => (
                    <tr key={task.id} className="border-t">
                      <td className="p-2">
                        <input
                          className="w-full border rounded px-2 py-1"
                          value={task.name}
                          onChange={e =>
                            updateTask(task.id, "name", e.target.value)
                          }
                        />
                      </td>

                      <td>
                        <select
                          value={task.priority}
                          onChange={e =>
                            updateTask(task.id, "priority", e.target.value)
                          }
                          className="border rounded px-2 py-1"
                        >
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                        </select>
                      </td>

                      <td>
                        <select
                          value={task.difficulty}
                          onChange={e =>
                            updateTask(task.id, "difficulty", e.target.value)
                          }
                          className="border rounded px-2 py-1"
                        >
                          <option value="easy">Easy</option>
                          <option value="medium">Medium</option>
                          <option value="hard">Hard</option>
                        </select>
                      </td>

                      <td>
                        <input
                          type="number"
                          className="border rounded px-2 py-1 w-20"
                          value={task.time}
                          onChange={e =>
                            updateTask(task.id, "time", e.target.value)
                          }
                        />
                      </td>

                      <td>
                        <button onClick={() => removeRow(task.id)}>
                          <Trash2 size={16} className="text-red-500" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="p-4 flex gap-4">
                <button onClick={addRow} className="border px-4 py-2 rounded-lg flex items-center gap-2">
                  <Plus size={16} /> Add Task
                </button>

                <button
                  onClick={analyzeDay}
                  className="bg-violet-600 text-white px-6 py-2 rounded-lg flex items-center gap-2"
                >
                  <Zap size={16} /> Optimize My Day
                </button>
              </div>
            </div>

            {/* AI Task Optimization */}
            {optimizedTasks.length > 0 && (
              <div className="bg-white/80 rounded-2xl p-6 border">
                <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                  <Sparkles className="text-violet-600" /> AI Task Optimization
                </h2>

                <table className="w-full text-sm border rounded-lg">
                  <thead className="bg-slate-100">
                    <tr>
                      <th className="p-2 text-left">Task</th>
                      <th className="p-2">Your Time</th>
                      <th className="p-2">AI Time</th>
                      <th className="p-2">Actual</th>
                    </tr>
                  </thead>

                  <tbody>
                    {optimizedTasks.map((t) => (
                      <tr key={t.id} className="border-t">
                        <td className="p-2">{t.name}</td>
                        <td className="text-center">{t.userTime}h</td>
                        <td className="text-center font-semibold text-violet-600">
                          {t.aiTime}h
                        </td>
                        <td className="text-center">
                          <input
                            type="number"
                            step="0.25"
                            placeholder="Actual"
                            className="border rounded px-2 py-1 w-20"
                            onChange={e =>
                              updateActualTime(t.id, e.target.value)
                            }
                          />
                          <button
                            className="ml-2 text-sm text-blue-600 hover:underline"
                            onClick={() => saveFeedback(t)}
                          >
                            Save
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Schedule */}
            {schedule.length > 0 && (
              <div className="bg-white/80 rounded-2xl p-6 border">
                <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                  <Clock className="text-violet-600" /> AI-Optimized Schedule
                </h2>

                {schedule.map((slot, i) => (
                  <div key={i} className="p-3 rounded-lg bg-violet-100 mb-2 flex items-center gap-2">
                    <div className="w-2 h-2 bg-violet-600 rounded-full"></div>
                    <strong>{slot.time}</strong> — {slot.task}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Column - AI Assistant (1/3 width) */}
          <div className="lg:col-span-1">
            <div className="bg-white/80 rounded-2xl border shadow-lg sticky top-24 flex flex-col h-[600px]">
              
              {/* Assistant Header */}
              <div className="p-4 border-b bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-t-2xl">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <Bot className="text-white" size={20} />
                  </div>
                  <div>
                    <h3 className="font-semibold">AI Coach</h3>
                    <p className="text-xs text-white/80">Your productivity partner</p>
                  </div>
                </div>
              </div>
              
              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-2xl p-3 ${
                        msg.type === 'user'
                          ? 'bg-violet-600 text-white'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      <p className="text-sm">{msg.message}</p>
                      
                      {/* Suggestions */}
                      {msg.suggestions && msg.suggestions.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {msg.suggestions.map((suggestion, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleQuickAction(suggestion)}
                              className="text-xs bg-white/20 hover:bg-white/30 rounded-full px-3 py-1 transition"
                            >
                              {suggestion}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 rounded-2xl p-3">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span>
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
              
              {/* Input Area */}
              <div className="p-4 border-t">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="Ask me anything..."
                    className="flex-1 border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={isLoading || !userInput.trim()}
                    className="bg-violet-600 text-white p-2 rounded-lg hover:bg-violet-700 transition disabled:opacity-50"
                  >
                    <Send size={18} />
                  </button>
                </div>
                
                {/* Quick action buttons */}
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => handleQuickAction("Plan my day")}
                    className="text-xs bg-gray-100 hover:bg-gray-200 rounded-full px-3 py-1 transition"
                  >
                    Plan Day
                  </button>
                  <button
                    onClick={() => handleQuickAction("Give me productivity advice")}
                    className="text-xs bg-gray-100 hover:bg-gray-200 rounded-full px-3 py-1 transition"
                  >
                    Advice
                  </button>
                  <button
                    onClick={() => handleQuickAction("Analyze my habits")}
                    className="text-xs bg-gray-100 hover:bg-gray-200 rounded-full px-3 py-1 transition"
                  >
                    Analyze
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Plan History */}
        {planHistory.length > 0 && (
          <div className="mt-12 bg-white/80 rounded-2xl p-6 border">
            <h2 className="text-2xl font-bold mb-4">Past Plans</h2>

            {planHistory.map((plan) => (
              <div key={plan._id} className="mb-6 border-b pb-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-semibold">Date: {plan.date}</h3>
                  <button
                    className="text-red-600 text-sm hover:underline"
                    onClick={() => deletePlan(plan._id)}
                  >
                    Delete
                  </button>
                </div>

                {plan.schedule && plan.schedule.map((slot, index) => (
                  <div key={index} className="text-sm text-gray-700">
                    {slot.time} — {slot.task}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </BackgroundLayout>
  );
};