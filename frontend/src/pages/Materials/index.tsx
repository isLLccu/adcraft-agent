import React, { useState } from 'react';
import { Card, Row, Col, Button, Space, Modal, Tag, Image, message, Select, Checkbox } from 'antd';
import { HeartOutlined, HeartFilled, DownloadOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { materialsApi } from '../../api/materials';
import { productsApi } from '../../api/products';
import type { Material } from '../../types';

export const Materials: React.FC = () => {
  const [selectedProduct, setSelectedProduct] = useState<number | undefined>();
  const [selectedPlatform, setSelectedPlatform] = useState<string | undefined>();
  const [showFavoriteOnly, setShowFavoriteOnly] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null);
  const queryClient = useQueryClient();

  const { data: materials, isLoading } = useQuery({
    queryKey: ['materials', selectedProduct, selectedPlatform, showFavoriteOnly],
    queryFn: async () => {
      const response = await materialsApi.getMaterials({
        product_id: selectedProduct,
        platform: selectedPlatform,
        is_favorite: showFavoriteOnly || undefined,
      });
      return response.data;
    },
  });

  const { data: products } = useQuery({
    queryKey: ['products'],
    queryFn: async () => {
      const response = await productsApi.getProducts();
      return response.data;
    },
  });

  const toggleFavoriteMutation = useMutation({
    mutationFn: ({ id, is_favorite }: { id: number; is_favorite: boolean }) =>
      materialsApi.toggleFavorite(id, is_favorite),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => materialsApi.deleteMaterial(id),
    onSuccess: () => {
      message.success('删除成功');
      queryClient.invalidateQueries({ queryKey: ['materials'] });
    },
    onError: () => {
      message.error('删除失败');
    },
  });

  const handleToggleFavorite = (material: Material) => {
    toggleFavoriteMutation.mutate({
      id: material.id,
      is_favorite: !material.is_favorite,
    });
  };

  const handleDownload = async (material: Material) => {
    try {
      const response = await materialsApi.downloadMaterial(material.id);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `material_${material.id}.png`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      message.success('下载成功');
    } catch (error) {
      message.error('下载失败');
    }
  };

  const handleViewDetail = async (material: Material) => {
    try {
      const response = await materialsApi.getMaterial(material.id);
      setSelectedMaterial(response.data);
      setDetailModalOpen(true);
    } catch (error) {
      message.error('获取详情失败');
    }
  };

  const getPlatformName = (platform: string) => {
    const platformMap: Record<string, string> = {
      xiaohongshu: '小红书',
      taobao: '淘宝',
      douyin: '抖音',
      wechat: '微信',
    };
    return platformMap[platform] || platform;
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Select
            placeholder="选择商品"
            allowClear
            style={{ width: 200 }}
            value={selectedProduct}
            onChange={setSelectedProduct}
            options={products?.map((product) => ({
              label: product.name,
              value: product.id,
            }))}
          />
          <Select
            placeholder="选择平台"
            allowClear
            style={{ width: 150 }}
            value={selectedPlatform}
            onChange={setSelectedPlatform}
            options={[
              { label: '小红书', value: 'xiaohongshu' },
              { label: '淘宝', value: 'taobao' },
              { label: '抖音', value: 'douyin' },
              { label: '微信', value: 'wechat' },
            ]}
          />
          <Checkbox
            checked={showFavoriteOnly}
            onChange={(e) => setShowFavoriteOnly(e.target.checked)}
          >
            只看收藏
          </Checkbox>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        {materials?.map((material) => (
          <Col key={material.id} xs={24} sm={12} md={8} lg={6}>
            <Card
              hoverable
              cover={
                <div style={{ height: 200, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0f0f0' }}>
                  <img
                    alt="素材"
                    src={material.image_url}
                    style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                  />
                </div>
              }
              actions={[
                <Button
                  type="text"
                  icon={material.is_favorite ? <HeartFilled style={{ color: '#ff4d4f' }} /> : <HeartOutlined />}
                  onClick={() => handleToggleFavorite(material)}
                />,
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={() => handleViewDetail(material)}
                />,
                <Button
                  type="text"
                  icon={<DownloadOutlined />}
                  onClick={() => handleDownload(material)}
                />,
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => {
                    Modal.confirm({
                      title: '确定要删除这个素材吗？',
                      onOk: () => deleteMutation.mutate(material.id),
                    });
                  }}
                />,
              ]}
            >
              <Card.Meta
                title={`素材 #${material.id}`}
                description={
                  <Space direction="vertical" size="small">
                    {material.task && (
                      <Tag color="blue">{getPlatformName(material.task.platform)}</Tag>
                    )}
                    <div style={{ fontSize: 12, color: '#999' }}>
                      {new Date(material.created_at).toLocaleString('zh-CN')}
                    </div>
                  </Space>
                }
              />
            </Card>
          </Col>
        ))}
      </Row>

      {!isLoading && materials?.length === 0 && (
        <div style={{ textAlign: 'center', padding: '50px 0', color: '#999' }}>
          暂无素材
        </div>
      )}

      <Modal
        title="素材详情"
        open={detailModalOpen}
        onCancel={() => setDetailModalOpen(false)}
        footer={null}
        width={800}
      >
        {selectedMaterial && (
          <div>
            <div style={{ textAlign: 'center', marginBottom: 24 }}>
              <Image src={selectedMaterial.image_url} style={{ maxWidth: '100%' }} />
            </div>

            {selectedMaterial.copy && (
              <div style={{ marginBottom: 16 }}>
                <h4>广告文案</h4>
                <p><strong>标题：</strong>{selectedMaterial.copy.title}</p>
                <p><strong>正文：</strong>{selectedMaterial.copy.body}</p>
                {selectedMaterial.copy.slogan && (
                  <p><strong>标语：</strong>{selectedMaterial.copy.slogan}</p>
                )}
              </div>
            )}

            {selectedMaterial.prompt && (
              <div style={{ marginBottom: 16 }}>
                <h4>图片 Prompt</h4>
                <p><strong>正向提示词：</strong>{selectedMaterial.prompt.prompt}</p>
                {selectedMaterial.prompt.negative_prompt && (
                  <p><strong>负向提示词：</strong>{selectedMaterial.prompt.negative_prompt}</p>
                )}
              </div>
            )}

            {selectedMaterial.product && (
              <div style={{ marginBottom: 16 }}>
                <h4>关联商品</h4>
                <p><strong>商品名称：</strong>{selectedMaterial.product.name}</p>
                <p><strong>价格：</strong>¥{selectedMaterial.product.price}</p>
              </div>
            )}

            <div>
              <h4>基本信息</h4>
              <p><strong>素材ID：</strong>{selectedMaterial.id}</p>
              <p><strong>创建时间：</strong>{new Date(selectedMaterial.created_at).toLocaleString('zh-CN')}</p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
