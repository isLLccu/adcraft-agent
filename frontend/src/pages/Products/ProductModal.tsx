import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, InputNumber, Select, Upload, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { productsApi } from '../../api/products';
import type { Product, Shop } from '../../types';
import type { UploadFile } from 'antd/es/upload/interface';

interface ProductModalProps {
  open: boolean;
  product: Product | null;
  shops: Shop[];
  onClose: () => void;
  onSuccess: () => void;
}

export const ProductModal: React.FC<ProductModalProps> = ({
  open,
  product,
  shops,
  onClose,
  onSuccess,
}) => {
  const [form] = Form.useForm();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (product) {
      form.setFieldsValue({
        ...product,
        selling_points: product.selling_points?.join('\n'),
        tags: product.tags?.join(','),
      });
      if (product.image_url) {
        setFileList([
          {
            uid: '-1',
            name: 'image.png',
            status: 'done',
            url: product.image_url,
          },
        ]);
      }
    } else {
      form.resetFields();
      setFileList([]);
    }
  }, [product, form]);

  const createMutation = useMutation({
    mutationFn: (data: any) => productsApi.createProduct(data),
    onSuccess: async (response) => {
      const productId = response.data.id;

      // 如果有新上传的图片，上传图片
      if (fileList.length > 0 && fileList[0].originFileObj) {
        setUploading(true);
        try {
          await productsApi.uploadImage(productId, fileList[0].originFileObj as File);
          message.success('商品创建成功');
          onSuccess();
        } catch (error) {
          message.error('图片上传失败');
        } finally {
          setUploading(false);
        }
      } else {
        message.success('商品创建成功');
        onSuccess();
      }
    },
    onError: () => {
      message.error('创建失败');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      productsApi.updateProduct(id, data),
    onSuccess: async () => {
      // 如果有新上传的图片，上传图片
      if (product && fileList.length > 0 && fileList[0].originFileObj) {
        setUploading(true);
        try {
          await productsApi.uploadImage(product.id, fileList[0].originFileObj as File);
          message.success('商品更新成功');
          onSuccess();
        } catch (error) {
          message.error('图片上传失败');
        } finally {
          setUploading(false);
        }
      } else {
        message.success('商品更新成功');
        onSuccess();
      }
    },
    onError: () => {
      message.error('更新失败');
    },
  });

  const handleOk = async () => {
    try {
      const values = await form.validateFields();

      const data = {
        ...values,
        selling_points: values.selling_points
          ? values.selling_points.split('\n').filter((s: string) => s.trim())
          : [],
        tags: values.tags
          ? values.tags.split(',').map((t: string) => t.trim()).filter((t: string) => t)
          : [],
      };

      if (product) {
        updateMutation.mutate({ id: product.id, data });
      } else {
        createMutation.mutate(data);
      }
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  const uploadButton = (
    <div>
      <PlusOutlined />
      <div style={{ marginTop: 8 }}>上传图片</div>
    </div>
  );

  return (
    <Modal
      title={product ? '编辑商品' : '添加商品'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={createMutation.isPending || updateMutation.isPending || uploading}
      width={600}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="shop_id"
          label="所属店铺"
          rules={[{ required: true, message: '请选择店铺' }]}
        >
          <Select
            placeholder="选择店铺"
            options={shops.map((shop) => ({
              label: shop.name,
              value: shop.id,
            }))}
          />
        </Form.Item>

        <Form.Item
          name="name"
          label="商品名称"
          rules={[{ required: true, message: '请输入商品名称' }]}
        >
          <Input placeholder="请输入商品名称" />
        </Form.Item>

        <Form.Item
          name="category"
          label="商品分类"
          rules={[{ required: true, message: '请输入商品分类' }]}
        >
          <Input placeholder="例如：服装、食品、电子产品" />
        </Form.Item>

        <Form.Item
          name="price"
          label="价格"
          rules={[{ required: true, message: '请输入价格' }]}
        >
          <InputNumber
            min={0}
            precision={2}
            style={{ width: '100%' }}
            placeholder="请输入价格"
            addonBefore="¥"
          />
        </Form.Item>

        <Form.Item name="description" label="商品描述">
          <Input.TextArea rows={3} placeholder="请输入商品描述" />
        </Form.Item>

        <Form.Item name="selling_points" label="卖点（每行一个）">
          <Input.TextArea rows={3} placeholder="例如：\n高品质材料\n性价比高\n包邮" />
        </Form.Item>

        <Form.Item name="target_audience" label="目标受众">
          <Input placeholder="例如：年轻女性、学生群体" />
        </Form.Item>

        <Form.Item name="usage_scenario" label="使用场景">
          <Input placeholder="例如：日常通勤、户外运动" />
        </Form.Item>

        <Form.Item name="tags" label="标签（逗号分隔）">
          <Input placeholder="例如：热销,新品,限时优惠" />
        </Form.Item>

        <Form.Item label="商品图片">
          <Upload
            listType="picture-card"
            fileList={fileList}
            beforeUpload={() => false}
            onChange={({ fileList }) => setFileList(fileList.slice(-1))}
            maxCount={1}
          >
            {fileList.length === 0 && uploadButton}
          </Upload>
        </Form.Item>
      </Form>
    </Modal>
  );
};
