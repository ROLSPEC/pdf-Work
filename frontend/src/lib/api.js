import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const t = localStorage.getItem("ughpdf_token");
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export const setToken = (t) => {
  if (t) localStorage.setItem("ughpdf_token", t);
  else localStorage.removeItem("ughpdf_token");
};

export const getToken = () => localStorage.getItem("ughpdf_token");
