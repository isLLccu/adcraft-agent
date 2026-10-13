import React, { useState } from 'react';
import { Table, Button, Space, Popconfirm, message, Input, Select, Tag } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productsApi } from '../../api/products';
import { shopsApi } from '../../api/shops';
import type { Product } from '../../types';
import { ProductModal } from './ProductModal';

export const Products: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [searchText, setSearchText] = useState('');
  const [selectedShop, setSelectedShop] = useState<number | undefined>();
  const queryClient = useQueryClient();

  const { data: products, isLoading } = useQuery({
    queryKey: ['products', selectedShop],
    queryFn: async () => {
      const response = await productsApi.getProducts({ shop_id: selectedShop });
      return response.data;
    },
  });

  const { data: shops } = useQuery({
    queryKey: ['shops'],
    queryFn: async () => {
      const response = await shopsApi.getShops();
      return response.data;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => productsApi.deleteProduct(id),
    onSuccess: () => {
      message.success('删除成功');
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
    onError: () => {
      message.error('删除失败');
    },
  });

  const handleAdd = () => {
    setEditingProduct(null);
    setIsModalOpen(true);
  };

  const handleEdit = (product: Product) => {
    setEditingProduct(product);
    setIsModalOpen(true);
  };

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id);
  };

  const filteredProducts = products?.filter((product) =>
    product.name.toLowerCase().includes(searchText.toLowerCase())
  );

  const columns = [
    {
      title: '商品图片',
      dataIndex: 'image_url',
      key: 'image_url',
      width: 100,
      render: (url: string) => (
        url ? <img src={url} alt="商品" style={{ width: 60, height: 60, objectFit: 'cover' }} /> : '-'
      ),
    },
    {
      title: '商品名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      render: (category: string) => <Tag color="blue">{category}</Tag>,
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (price: number | string) => `¥${Number(price).toFixed(2)}`,
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
      render: (_: any, record: Product) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个商品吗？"
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
        <Space>
          <Input
            placeholder="搜索商品名称"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 200 }}
          />
          <Select
            placeholder="选择店铺"
            allowClear
            style={{ width: 200 }}
            value={selectedShop}
            onChange={setSelectedShop}
            options={shops?.map((shop) => ({
              label: shop.name,
              value: shop.id,
            }))}
          />
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加商品
        </Button>
      </div>

      <Table
        dataSource={filteredProducts}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 10 }}
      />

      <ProductModal
        open={isModalOpen}
        product={editingProduct}
        shops={shops || []}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
          setIsModalOpen(false);
          queryClient.invalidateQueries({ queryKey: ['products'] });
        }}
      />
    </div>
  );
};
