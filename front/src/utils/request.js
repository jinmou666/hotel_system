import axios from 'axios';

const request = axios.create({
  baseURL: 'http://127.0.0.1:5000/api',
  timeout: 30000, // 核心修改：从 5000 改为 30000，防止并发操作时超时
});

request.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
);

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('接口请求失败：', error.message);
    return Promise.reject(error);
  }
);

export default request;