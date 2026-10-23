import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { App as AntdApp } from 'antd'
import './index.css'
import App from './App.tsx'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{
      token: { colorPrimary: '#5363df', colorLink: '#6273cd', colorText: '#3d4965', colorTextSecondary: '#697892',
        colorBorder: '#e0e6f1', colorBgLayout: '#f7f8fc', borderRadius: 9, borderRadiusLG: 12,
        fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif", controlHeight: 37 },
      components: { Button: { primaryShadow: '0 3px 9px rgba(83,99,223,.14)' }, Card: { headerBg: '#fdfdff' },
        Modal: { titleColor: '#303c59' }, Tabs: { horizontalItemGutter: 28 }, Alert: { withDescriptionPadding: '14px 16px' } },
    }}>
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
)
