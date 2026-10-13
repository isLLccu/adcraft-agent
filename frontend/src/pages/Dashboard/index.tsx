import React from 'react';
import { Row, Col, Card, Statistic, Table, Button } from 'antd';
import { ArrowUpOutlined, PlusOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { statsApi } from '../../api/stats';
import { tasksApi } from '../../api/tasks';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const { data: overview } = useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: async () => {
      const response = await statsApi.getOverview();
      return response.data;
    },
  });

  const { data: tasks } = useQuery({
    queryKey: ['tasks', 'recent'],
    queryFn: async () => {
      const response = await tasksApi.getTasks({ limit: 10 });
      return response.data;
    },
  });

  const columns = [
    {
      title: '任务ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: Record<string, string> = {
          pending: '等待中',
          processing: '处理中',
          completed: '已完成',
          failed: '失败',
        };
        return statusMap[status] || status;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
  ];

  return (
    <div>
      <h1>控制台</h1>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总任务数"
              value={overview?.total_tasks || 0}
              prefix={<ArrowUpOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="成功任务"
              value={overview?.success_tasks || 0}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="成功率"
              value={overview?.success_rate || 0}
              suffix="%"
              precision={2}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="素材总数"
              value={overview?.total_materials || 0}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="最近任务"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/tasks')}>
            创建任务
          </Button>
        }
      >
        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="id"
          pagination={false}
        />
      </Card>
    </div>
  );
};
