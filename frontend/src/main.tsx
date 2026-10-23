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
      token: { colorPrimary: '#168b78', colorInfo: '#168b78', colorLink: '#168b78', colorText: '#344d49', colorTextSecondary: '#667874',
        colorBorder: '#dce7e4', colorBgLayout: '#f3f6f8', borderRadius: 9, borderRadiusLG: 12,
        fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif", controlHeight: 37 },
      components: { Button: { primaryShadow: '0 3px 9px rgba(22,139,120,.14)' }, Card: { headerBg: '#fcfdfc' },
        Modal: { titleColor: '#253e3a' }, Tabs: { horizontalItemGutter: 28 }, Alert: { withDescriptionPadding: '14px 16px' } },
    }}>
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
)
