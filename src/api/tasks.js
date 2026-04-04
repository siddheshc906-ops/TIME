import { getToken } from "./auth";

const BASE_URL = process.env.REACT_APP_BACKEND_URL;

function authHeader() {
  const token = getToken();

  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function getTasks() {
  const res = await fetch(`${BASE_URL}/api/tasks`, {
    headers: authHeader(),
  });

  return res.json();
}

export async function createTask(task) {
  const res = await fetch(`${BASE_URL}/api/tasks`, {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify(task),
  });

  return res.json();
}

export async function deleteTask(id) {
  await fetch(`${BASE_URL}/api/tasks/${id}`, {
    method: "DELETE",
    headers: authHeader(),
  });
}

export async function updateTask(id, data) {
  await fetch(`${BASE_URL}/api/tasks/${id}`, {
    method: "PUT",
    headers: authHeader(),
    body: JSON.stringify(data),
  });
}