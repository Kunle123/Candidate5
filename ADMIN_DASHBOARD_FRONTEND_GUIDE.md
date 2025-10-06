# Admin Dashboard - Frontend Integration Guide

## 📋 Overview

Build a React-based admin panel to manage users, adjust credits, view profiles, and monitor analytics for the CandidateV platform.

---

## ✅ Quick Setup Checklist

Before you start building, ensure you have:

1. **API Gateway URL:** `https://api-gw-production.up.railway.app`
2. **Admin Service URL (via Gateway):** `/api/admin/*`
3. **Direct Admin Service URL:** `https://adminservice-production-551a.up.railway.app` (for testing only)
4. **Initial Super Admin Credentials:** (Ask backend team to create the first admin account)
5. **Test the health endpoint:** `curl https://adminservice-production-551a.up.railway.app/health`

### Backend Status:
- ✅ Admin Service deployed and running
- ✅ Database tables created (admins, credit_transactions, admin_audit_logs)
- ✅ API Gateway configured with `/api/admin/*` routes
- ⏳ **NEXT:** Create initial super admin account
- ⏳ **THEN:** Build frontend UI

---

## 🎯 What to Build

### Phase 1 (MVP) - Pages & Features

1. **Login Page** (`/admin/login`)
   - Email & password fields
   - Remember me checkbox
   - Error handling for invalid credentials
   
2. **Dashboard** (`/admin/dashboard`)
   - Analytics overview cards
   - Charts for signups, CVs, applications
   - Quick actions

3. **Users List** (`/admin/users`)
   - Paginated table
   - Search by email/name
   - Columns: Email, Name, Credits, Subscription, Created Date
   - Actions: View Details, Adjust Credits

4. **User Detail Page** (`/admin/users/:id`)
   - User information card
   - Credit adjustment form
   - Credit transaction history
   - Quick actions (View Profile, View Activity)

5. **Career Arc Viewer** (`/admin/users/:id/profile`)
   - Display complete user profile
   - Work experience, education, skills, etc.
   - Download profile as JSON option

6. **User Activity** (`/admin/users/:id/activity`)
   - CVs generated (list with dates)
   - Applications submitted (list with job titles)

---

## 🔐 Authentication Flow

### 1. Login

**Endpoint:** `POST /api/admin/auth/login`

```typescript
interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  admin: {
    id: string;
    email: string;
    name: string;
    role: "super_admin" | "admin" | "support";
    is_active: boolean;
    created_at: string;
    last_login: string;
  };
}
```

**Implementation:**

```typescript
// src/services/adminAuth.ts
import axios from 'axios';

const API_BASE_URL = 'https://api-gw-production.up.railway.app';
// Admin service is accessible through the API Gateway at /api/admin/*

export const adminLogin = async (email: string, password: string) => {
  const response = await axios.post(`${API_BASE_URL}/api/admin/auth/login`, {
    email,
    password
  });
  
  // Store token in localStorage
  localStorage.setItem('admin_token', response.data.access_token);
  localStorage.setItem('admin_user', JSON.stringify(response.data.admin));
  
  return response.data;
};

export const adminLogout = async () => {
  const token = localStorage.getItem('admin_token');
  
  if (token) {
    await axios.post(`${API_BASE_URL}/api/admin/auth/logout`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
  }
  
  localStorage.removeItem('admin_token');
  localStorage.removeItem('admin_user');
};

export const getCurrentAdmin = async () => {
  const token = localStorage.getItem('admin_token');
  
  if (!token) throw new Error('No token found');
  
  const response = await axios.get(`${API_BASE_URL}/api/admin/auth/me`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  
  return response.data;
};

export const getAdminToken = () => localStorage.getItem('admin_token');
export const isAdminAuthenticated = () => !!getAdminToken();
```

### 2. Protected Routes

```typescript
// src/components/AdminRoute.tsx
import { Navigate } from 'react-router-dom';
import { isAdminAuthenticated } from '../services/adminAuth';

export const AdminRoute = ({ children }: { children: React.ReactNode }) => {
  if (!isAdminAuthenticated()) {
    return <Navigate to="/admin/login" replace />;
  }
  
  return <>{children}</>;
};
```

### 3. Axios Interceptor (Auto-attach token)

```typescript
// src/services/adminApi.ts
import axios from 'axios';
import { getAdminToken } from './adminAuth';

const adminApi = axios.create({
  baseURL: 'https://api-gw-production.up.railway.app/api/admin'
});

// Request interceptor to add auth token
adminApi.interceptors.request.use(
  (config) => {
    const token = getAdminToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle 401 errors
adminApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      window.location.href = '/admin/login';
    }
    return Promise.reject(error);
  }
);

export default adminApi;
```

---

## 📊 API Endpoints & TypeScript Interfaces

### User Management

#### List Users

```typescript
// GET /api/admin/users/?skip=0&limit=50&search=john
interface UserListItem {
  id: string;
  email: string;
  name: string | null;
  monthly_credits_remaining: number;
  topup_credits: number;
  subscription_type: string;
  created_at: string;
  last_monthly_reset: string | null;
}

const listUsers = async (skip = 0, limit = 50, search = '') => {
  const response = await adminApi.get('/users/', {
    params: { skip, limit, search }
  });
  return response.data as UserListItem[];
};
```

#### Get User Detail

```typescript
// GET /api/admin/users/:id
interface UserDetail {
  id: string;
  email: string;
  name: string | null;
  address_line1: string | null;
  city_state_postal: string | null;
  linkedin: string | null;
  phone_number: string | null;
  monthly_credits_remaining: number;
  daily_credits_remaining: number;
  topup_credits: number;
  subscription_type: string;
  created_at: string;
  updated_at: string;
  last_daily_reset: string | null;
  last_monthly_reset: string | null;
  next_credit_reset: string | null;
}

const getUserDetail = async (userId: string) => {
  const response = await adminApi.get(`/users/${userId}`);
  return response.data as UserDetail;
};
```

#### Adjust Credits

```typescript
// POST /api/admin/users/:id/credits
interface CreditAdjustmentRequest {
  amount: number;  // Positive to add, negative to deduct
  reason: 'Refund' | 'Promo' | 'Support' | 'Correction' | 'Violation';
  notes?: string;
}

interface CreditTransaction {
  id: number;
  user_id: string;
  admin_id: string;
  amount: number;
  reason: string;
  notes: string | null;
  balance_before: number;
  balance_after: number;
  created_at: string;
}

const adjustCredits = async (userId: string, adjustment: CreditAdjustmentRequest) => {
  const response = await adminApi.post(`/users/${userId}/credits`, adjustment);
  return response.data;
};
```

#### Get Credit History

```typescript
// GET /api/admin/users/:id/credits/history
const getCreditHistory = async (userId: string) => {
  const response = await adminApi.get(`/users/${userId}/credits/history`);
  return response.data as CreditTransaction[];
};
```

#### Get User Career Arc

```typescript
// GET /api/admin/users/:id/profile
interface WorkExperience {
  id: string;
  company: string;
  title: string;
  start_date: string;
  end_date: string;
  location: string;
  description: string[];
}

interface Education {
  id: string;
  institution: string;
  degree: string;
  field: string;
  start_date: string;
  end_date: string;
}

interface UserProfile {
  work_experience: WorkExperience[];
  education: Education[];
  skills: Array<{ skill: string }>;
  projects: Array<{ name: string; description: string }>;
  certifications: Array<{ name: string; issuer: string; year: string }>;
  languages: string[];
  interests: string[];
}

const getUserProfile = async (userId: string) => {
  const response = await adminApi.get(`/users/${userId}/profile`);
  return response.data as UserProfile;
};
```

#### Get User Activity

```typescript
// GET /api/admin/users/:id/activity
interface UserActivity {
  user_id: string;
  cvs_count: number;
  cvs: Array<{
    id: string;
    created_at: string;
    job_title: string;
  }>;
  applications_count: number;
  applications: Array<{
    id: string;
    job_title: string;
    company_name: string;
    applied_at: string;
    status: string;
  }>;
}

const getUserActivity = async (userId: string) => {
  const response = await adminApi.get(`/users/${userId}/activity`);
  return response.data as UserActivity;
};
```

### Analytics

```typescript
// GET /api/admin/analytics/summary
interface AnalyticsSummary {
  total_users: number;
  active_users_7d: number;
  active_users_30d: number;
  new_signups_7d: number;
  new_signups_30d: number;
  total_cvs_generated: number;
  cvs_generated_7d: number;
  cvs_generated_30d: number;
  total_applications: number;
  applications_7d: number;
  applications_30d: number;
  total_credits_purchased: number;
  total_credits_consumed: number;
}

const getAnalytics = async () => {
  const response = await adminApi.get('/analytics/summary');
  return response.data as AnalyticsSummary;
};
```

---

## 🎨 UI Components Library

### Recommended: Ant Design

```bash
npm install antd @ant-design/icons
```

**Why Ant Design?**
- Ready-made admin components (Table, Form, Card, Modal)
- Professional look and feel
- Excellent documentation
- Great TypeScript support

### Alternative: Material-UI

```bash
npm install @mui/material @mui/icons-material @emotion/react @emotion/styled
```

---

## 📄 Page Components

### 1. Login Page

```typescript
// src/pages/admin/Login.tsx
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { adminLogin } from '../../services/adminAuth';

export const AdminLogin = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { email: string; password: string }) => {
    setLoading(true);
    try {
      await adminLogin(values.email, values.password);
      message.success('Login successful!');
      navigate('/admin/dashboard');
    } catch (error) {
      message.error('Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f0f2f5' }}>
      <Card title="Admin Login" style={{ width: 400 }}>
        <Form onFinish={onFinish}>
          <Form.Item name="email" rules={[{ required: true, type: 'email' }]}>
            <Input prefix={<UserOutlined />} placeholder="Email" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Login
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};
```

### 2. Dashboard

```typescript
// src/pages/admin/Dashboard.tsx
import { Card, Row, Col, Statistic, Spin } from 'antd';
import { UserOutlined, FileTextOutlined, SendOutlined, DollarOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { getAnalytics } from '../../services/adminApi';

export const AdminDashboard = () => {
  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: getAnalytics
  });

  if (isLoading) return <Spin size="large" />;

  return (
    <div>
      <h1>Dashboard</h1>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total Users"
              value={analytics?.total_users}
              prefix={<UserOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="New Signups (7d)"
              value={analytics?.new_signups_7d}
              prefix={<UserOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="CVs Generated"
              value={analytics?.total_cvs_generated}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Applications"
              value={analytics?.total_applications}
              prefix={<SendOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};
```

### 3. Users List

```typescript
// src/pages/admin/UsersList.tsx
import { Table, Input, Button, Space, Tag } from 'antd';
import { SearchOutlined, EyeOutlined, DollarOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { listUsers } from '../../services/adminApi';

export const UsersList = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const { data: users, isLoading } = useQuery({
    queryKey: ['users', page, search],
    queryFn: () => listUsers((page - 1) * pageSize, pageSize, search)
  });

  const columns = [
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Credits',
      key: 'credits',
      render: (record: UserListItem) => (
        <span>{record.monthly_credits_remaining + record.topup_credits}</span>
      ),
    },
    {
      title: 'Subscription',
      dataIndex: 'subscription_type',
      key: 'subscription_type',
      render: (sub: string) => (
        <Tag color={sub === 'pro' ? 'blue' : 'default'}>{sub}</Tag>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (record: UserListItem) => (
        <Space>
          <Button
            icon={<EyeOutlined />}
            onClick={() => navigate(`/admin/users/${record.id}`)}
          >
            View
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <h1>Users</h1>
      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="Search by email or name"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 300 }}
        />
      </Space>
      <Table
        columns={columns}
        dataSource={users}
        loading={isLoading}
        rowKey="id"
        pagination={{
          current: page,
          pageSize,
          onChange: setPage,
        }}
      />
    </div>
  );
};
```

### 4. User Detail with Credit Adjustment

```typescript
// src/pages/admin/UserDetail.tsx
import { Card, Descriptions, Button, Modal, Form, InputNumber, Select, Input, message } from 'antd';
import { DollarOutlined, UserOutlined, FileTextOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getUserDetail, adjustCredits } from '../../services/adminApi';
import { useState } from 'react';

export const UserDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [creditModalOpen, setCreditModalOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: user, isLoading } = useQuery({
    queryKey: ['user', id],
    queryFn: () => getUserDetail(id!)
  });

  const adjustCreditsMutation = useMutation({
    mutationFn: (values: any) => adjustCredits(id!, values),
    onSuccess: () => {
      message.success('Credits adjusted successfully');
      setCreditModalOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['user', id] });
    },
    onError: () => {
      message.error('Failed to adjust credits');
    }
  });

  if (isLoading || !user) return <div>Loading...</div>;

  return (
    <div>
      <h1>User Detail</h1>
      <Card
        title={user.name || user.email}
        extra={
          <Button
            type="primary"
            icon={<DollarOutlined />}
            onClick={() => setCreditModalOpen(true)}
          >
            Adjust Credits
          </Button>
        }
      >
        <Descriptions column={2}>
          <Descriptions.Item label="Email">{user.email}</Descriptions.Item>
          <Descriptions.Item label="Subscription">{user.subscription_type}</Descriptions.Item>
          <Descriptions.Item label="Monthly Credits">{user.monthly_credits_remaining}</Descriptions.Item>
          <Descriptions.Item label="Topup Credits">{user.topup_credits}</Descriptions.Item>
          <Descriptions.Item label="Total Credits">
            {user.monthly_credits_remaining + user.topup_credits}
          </Descriptions.Item>
          <Descriptions.Item label="Created">
            {new Date(user.created_at).toLocaleString()}
          </Descriptions.Item>
        </Descriptions>
        <Space style={{ marginTop: 16 }}>
          <Button
            icon={<UserOutlined />}
            onClick={() => navigate(`/admin/users/${id}/profile`)}
          >
            View Career Arc
          </Button>
          <Button
            icon={<FileTextOutlined />}
            onClick={() => navigate(`/admin/users/${id}/activity`)}
          >
            View Activity
          </Button>
        </Space>
      </Card>

      <Modal
        title="Adjust Credits"
        open={creditModalOpen}
        onCancel={() => setCreditModalOpen(false)}
        footer={null}
      >
        <Form
          form={form}
          onFinish={(values) => adjustCreditsMutation.mutate(values)}
        >
          <Form.Item
            name="amount"
            label="Amount"
            rules={[{ required: true }]}
            extra="Positive to add, negative to deduct"
          >
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="reason" label="Reason" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="Refund">Refund</Select.Option>
              <Select.Option value="Promo">Promo</Select.Option>
              <Select.Option value="Support">Support</Select.Option>
              <Select.Option value="Correction">Correction</Select.Option>
              <Select.Option value="Violation">Violation</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="notes" label="Notes">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={adjustCreditsMutation.isPending}>
              Adjust Credits
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
```

---

## 🔧 Setup Instructions

### 1. Install Dependencies

```bash
npm install antd @ant-design/icons
npm install @tanstack/react-query
npm install react-router-dom
npm install axios
```

### 2. Project Structure

```
src/
├── pages/
│   └── admin/
│       ├── Login.tsx
│       ├── Dashboard.tsx
│       ├── UsersList.tsx
│       ├── UserDetail.tsx
│       ├── UserProfile.tsx
│       └── UserActivity.tsx
├── services/
│   ├── adminAuth.ts
│   └── adminApi.ts
├── components/
│   ├── AdminLayout.tsx
│   └── AdminRoute.tsx
└── App.tsx
```

### 3. Router Setup

```typescript
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AdminRoute } from './components/AdminRoute';
import { AdminLayout } from './components/AdminLayout';
import { AdminLogin, AdminDashboard, UsersList, UserDetail } from './pages/admin';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
          <Route index element={<AdminDashboard />} />
          <Route path="dashboard" element={<AdminDashboard />} />
          <Route path="users" element={<UsersList />} />
          <Route path="users/:id" element={<UserDetail />} />
          <Route path="users/:id/profile" element={<UserProfile />} />
          <Route path="users/:id/activity" element={<UserActivity />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

---

## ✅ Testing Checklist

- [ ] Admin can login with correct credentials
- [ ] Invalid credentials show error message
- [ ] Token is stored in localStorage
- [ ] Token is auto-attached to all API requests
- [ ] Expired token redirects to login
- [ ] Dashboard shows correct analytics
- [ ] Users list loads and displays data
- [ ] Search filters users correctly
- [ ] Pagination works
- [ ] User detail page shows correct info
- [ ] Credit adjustment modal works
- [ ] Credit history displays transactions
- [ ] Career arc viewer shows full profile
- [ ] User activity shows CVs and applications
- [ ] Logout clears token and redirects to login

---

## 🚀 Deployment

1. Build the admin frontend
2. Deploy to Vercel/Netlify
3. Add allowed origin to API Gateway CORS
4. Test in production

---

## 📞 Support

If you have any questions, reach out to the backend team with the endpoint you're trying to integrate.

Happy coding! 🎉

