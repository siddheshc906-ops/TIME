// frontend/src/utils/testData.js

export const sampleTasks = [
  { text: "Complete project proposal", priority: "high", completed: true },
  { text: "Review team updates", priority: "medium", completed: true },
  { text: "Prepare presentation", priority: "high", completed: false },
  { text: "Schedule meeting with client", priority: "medium", completed: true },
  { text: "Update documentation", priority: "low", completed: false },
  { text: "Code review", priority: "high", completed: true },
  { text: "Team lunch", priority: "low", completed: true },
  { text: "Research new tools", priority: "medium", completed: false },
  { text: "Write blog post", priority: "medium", completed: true },
  { text: "Fix navigation bug", priority: "high", completed: true },
  { text: "Design review", priority: "medium", completed: false },
  { text: "Client call", priority: "high", completed: true },
  { text: "Update resume", priority: "low", completed: false },
  { text: "Learn new framework", priority: "medium", completed: false },
  { text: "Exercise", priority: "medium", completed: true },
];

export const sampleWeekTasks = {
  monday: [
    { id: 1, text: "Team meeting", completed: true },
    { id: 2, text: "Project planning", completed: true },
    { id: 3, text: "Code review", completed: false },
  ],
  tuesday: [
    { id: 4, text: "Client presentation", completed: true },
    { id: 5, text: "Documentation", completed: false },
  ],
  wednesday: [
    { id: 6, text: "Development sprint", completed: true },
    { id: 7, text: "Testing", completed: true },
    { id: 8, text: "Deployment", completed: false },
  ],
  thursday: [
    { id: 9, text: "Team building", completed: true },
    { id: 10, text: "Performance review", completed: false },
  ],
  friday: [
    { id: 11, text: "Weekly summary", completed: false },
    { id: 12, text: "Planning next week", completed: false },
  ],
  saturday: [
    { id: 13, text: "Personal project", completed: true },
  ],
  sunday: [
    { id: 14, text: "Rest and recharge", completed: false },
  ],
};

export const sampleAnalytics = {
  overview: {
    total_tasks: 186,
    completed: 145,
    completion_rate: 78.5,
    high_priority_tasks: 45,
    avg_task_duration: 1.5
  },
  tasks_by_priority: { high: 45, medium: 78, low: 63 },
  tasks_by_difficulty: { easy: 62, medium: 58, hard: 66 },
  daily: generateDailyData(30),
  recommendations: [
    "Schedule complex tasks in the morning for better focus",
    "Take breaks between 2-4pm when energy naturally dips",
    "You're most productive on Tuesdays - plan important work then",
    "Break down large tasks into smaller 25-minute chunks",
    "Try the Pomodoro technique for better focus"
  ]
};

function generateDailyData(days) {
  const data = [];
  for (let i = days; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    data.push({
      date: date.toISOString().split('T')[0],
      total: Math.floor(Math.random() * 8) + 3,
      completed: Math.floor(Math.random() * 6) + 2,
      focus_hours: (Math.random() * 4 + 2).toFixed(1)
    });
  }
  return data;
}