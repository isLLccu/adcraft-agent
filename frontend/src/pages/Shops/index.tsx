import React, { useState } from 'react';
import { Table, Button, Space, Popconfirm, message, Modal, Form, Input } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { shopsApi } from '../../api/shops';
import type { Shop } from '../../types';

export const Shops: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingShop, setEditingShop] = useState<Shop | null>(null);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: shops, isLoading } = useQuery({
    queryKey: ['shops'],
    queryFn: async () => {
      const response = await shopsApi.getShops();
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => shopsApi.createShop(data),
    onSuccess: () => {
      message.success('创建成功');
      queryClient.invalidateQueries({ queryKey: ['shops'] });
      setIsModalOpen(false);
      form.resetFields();
    },
    onError: () => {
      message.error('创建失败');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      shopsApi.updateShop(id, data),
    onSuccess: () => {
      message.success('更新成功');
      queryClient.invalidateQueries({ queryKey: ['shops'] });
      setIsModalOpen(false);
      form.resetFields();
    },
    onError: () => {
      message.error('更新失败');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => shopsApi.deleteShop(id),
    onSuccess: () => {
      message.success('删除成功');
      queryClient.invalidateQueries({ queryKey: ['shops'] });
    },
    onError: () => {
      message.error('删除失败');
    },
  });

  const handleAdd = () => {
    setEditingShop(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const handleEdit = (shop: Shop) => {
    setEditingShop(shop);
    form.setFieldsValue(shop);
    setIsModalOpen(true);
  };

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingShop) {
        updateMutation.mutate({ id: editingShop.id, data: values });
      } else {
        createMutation.mutate(values);
      }
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  const columns = [
    {
      title: '店铺名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '行业',
      dataIndex: 'industry',
      key: 'industry',
    },
    {
      title: '主要平台',
      dataIndex: 'main_platform',
      key: 'main_platform',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
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
      width: 150,
      render: (_: any, record: Shop) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个店铺吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2>店铺管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加店铺
        </Button>
      </div>

      <Table
        dataSource={shops}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={editingShop ? '编辑店铺' : '添加店铺'}
        open={isModalOpen}
        onOk={handleOk}
        onCancel={() => {
          setIsModalOpen(false);
          form.resetFields();
        }}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="店铺名称"
            rules={[{ required: true, message: '请输入店铺名称' }]}
          >
            <Input placeholder="请输入店铺名称" />
          </Form.Item>

          <Form.Item name="industry" label="行业">
            <Input placeholder="例如：服装、食品、电子产品" />
          </Form.Item>

          <Form.Item name="brand_style" label="品牌风格">
            <Input placeholder="例如：时尚、简约、复古" />
          </Form.Item>

          <Form.Item name="target_audience" label="目标受众">
            <Input placeholder="例如：年轻女性、学生群体" />
          </Form.Item>

          <Form.Item name="main_platform" label="主要平台">
            <Input placeholder="例如：淘宝、京东、抖音" />
          </Form.Item>

          <Form.Item name="description" label="店铺描述">
            <Input.TextArea rows={3} placeholder="请输入店铺描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
