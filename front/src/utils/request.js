import axios from 'axios';

const request = axios.create({
  baseURL: 'http://127.0.0.1:5000/api', // 后端接口基础路径
  timeout: 5000,
});

// 请求拦截器（可选）
request.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('接口请求失败：', error.message);
    return Promise.reject(error);
  }
);

export default request;