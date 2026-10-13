import React, { useState } from 'react';
import { Table, Button, Space, Tag, Modal, Form, Select, Radio, Input, Popconfirm, message } from 'antd';
import { PlusOutlined, EyeOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tasksApi } from '../../api/tasks';
import { productsApi } from '../../api/products';
import type { AdTask, Product } from '../../types';

export const Tasks: React.FC = () => {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: async () => {
      const response = await tasksApi.getTasks();
      return response.data;
    },
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasPendingTasks = data?.some(
        (task: AdTask) => task.status === 'pending' || task.status === 'processing'
      );
      return hasPendingTasks ? 3000 : false;
    },
  });

  const { data: products } = useQuery({
    queryKey: ['products', 'for-task'],
    queryFn: async () => {
      const response = await productsApi.getProducts();
      return response.data;
    },
    enabled: isCreateModalOpen,
    staleTime: 0,
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => tasksApi.createTask(data),
    onSuccess: () => {
      message.success('任务已提交，AI 正在生成素材...');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setIsCreateModalOpen(false);
      form.resetFields();
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail;
      console.error('创建任务失败:', detail);
      let msg = '任务创建失败';
      if (typeof detail === 'string') {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0];
        const field = Array.isArray(first?.loc) ? first.loc.slice(1).join('.') : '字段';
        msg = `${field}: ${first?.msg ?? '验证失败'}`;
      }
      message.error(msg);
    },
  });

  const retryMutation = useMutation({
    mutationFn: (id: number) => tasksApi.retryTask(id),
    onSuccess: () => {
      message.success('任务已重新提交');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: () => {
      message.error('重试失败');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => tasksApi.deleteTask(id),
    onSuccess: () => {
      message.success('任务已删除');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: () => {
      message.error('删除失败');
    },
  });

  const handleCreate = () => {
    form.resetFields();
    setIsCreateModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const productId = Number(values.product_id);
      const product = products?.find((p: Product) => Number(p.id) === productId);
      if (!product) {
        message.error('找不到所选商品，请重新选择');
        return;
      }
      createMutation.mutate({
        ...values,
        product_id: productId,
        shop_id: product.shop_id,
      });
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '排队中' },
      processing: { color: 'processing', text: '生成中' },
      completed: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' },
    };
    const config = statusMap[status] || { color: 'default', text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const columns = [
    { title: '任务ID', dataIndex: 'id', key: 'id', width: 80 },
    {
      title: '广告类型',
      dataIndex: 'ad_type',
      key: 'ad_type',
      render: (t: string) => {
        const m: Record<string, string> = {
          main_image: '主图',
          new_product: '新品推广',
          promotion: '促销活动',
          festival: '节日营销',
          seed_note: '种草笔记',
          activity_poster: '活动海报',
        };
        return m[t] || t;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      render: (_: any, record: AdTask) => (
        <Space>
          <Button type="link" icon={<EyeOutlined />} onClick={() => message.info('请到「素材库」查看生成结果')}>
            查看
          </Button>
          {record.status === 'failed' && (
            <Button type="link" icon={<ReloadOutlined />} onClick={() => retryMutation.mutate(record.id)}>
              重试
            </Button>
          )}
          <Popconfirm
            title="确定要删除这个任务吗？"
            description="任务及其生成的所有素材都将被删除"
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2>任务中心</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          一键生成广告素材
        </Button>
      </div>

      <Table
        dataSource={tasks}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="一键生成广告素材"
        open={isCreateModalOpen}
        onCancel={() => {
          setIsCreateModalOpen(false);
          form.resetFields();
        }}
        onOk={handleSubmit}
        okText="开始生成 (6 张图)"
        cancelText="取消"
        confirmLoading={createMutation.isPending}
        width={620}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            platform: 'xiaohongshu',
            ad_type: 'main_image',
            image_ratio: '1:1',
          }}
          // 平台用 Form.Item hidden 提交，不出现在 UI 上
        >
          <Form.Item
            name="product_id"
            label="选择商品"
            rules={[{ required: true, message: '请选择商品' }]}
            extra={!products?.length ? '请先到「商品管理」创建商品' : undefined}
          >
            <Select
              placeholder="选择要推广的商品"
              options={products?.map((product: Product) => ({
                label: `${product.name} - ¥${Number(product.price).toFixed(2)}`,
                value: product.id,
              })) ?? []}
            />
          </Form.Item>

          <Form.Item name="platform" hidden>
            <Input />
          </Form.Item>

          <Form.Item
            name="ad_type"
            label="广告类型"
            rules={[{ required: true, message: '请选择广告类型' }]}
          >
            <Select
              options={[
                { label: '主图', value: 'main_image' },
                { label: '新品推广', value: 'new_product' },
                { label: '促销活动', value: 'promotion' },
                { label: '节日营销', value: 'festival' },
                { label: '种草笔记', value: 'seed_note' },
                { label: '活动海报', value: 'activity_poster' },
              ]}
            />
          </Form.Item>

          <Form.Item
            name="image_ratio"
            label="主图比例"
            rules={[{ required: true, message: '请选择图片比例' }]}
            extra="任务会自动生成主图、详情图、长图等多种规格"
          >
            <Radio.Group>
              <Radio.Button value="1:1">1:1</Radio.Button>
              <Radio.Button value="3:4">3:4</Radio.Button>
              <Radio.Button value="4:5">4:5</Radio.Button>
              <Radio.Button value="9:16">9:16</Radio.Button>
              <Radio.Button value="16:9">16:9</Radio.Button>
            </Radio.Group>
          </Form.Item>

          <Form.Item name="style" label="画面风格 (可选)">
            <Select
              placeholder="不选则由 AI 自由发挥"
              allowClear
              options={[
                { label: '清新自然', value: '清新自然' },
                { label: '时尚潮流', value: '时尚潮流' },
                { label: '简约高级', value: '简约高级' },
                { label: '复古怀旧', value: '复古怀旧' },
                { label: '科技未来', value: '科技未来' },
              ]}
            />
          </Form.Item>

          <Form.Item name="copywriting_tone" label="文案语气 (可选)">
            <Select
              placeholder="不选则由 AI 自由发挥"
              allowClear
              options={[
                { label: '友好亲切', value: '友好' },
                { label: '专业权威', value: '专业' },
                { label: '活泼生动', value: '活泼' },
                { label: '正式严谨', value: '正式' },
              ]}
            />
          </Form.Item>

          <Form.Item name="extra_prompt" label="补充描述 (可选)">
            <Input.TextArea
              rows={2}
              placeholder="例如：突出夏日海边场景、强调环保材质..."
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
