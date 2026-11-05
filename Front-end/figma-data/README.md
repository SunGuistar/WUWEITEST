# Figma 设计数据提取结果

## 状态：REST API 验证成功 + 阶段二数据整理完成

目标文件：

- URL: https://www.figma.com/design/D0jjN7Twkq0DGm3ZJvQabz/前端工程师（实习）?node-id=0-1&p=f
- fileKey: D0jjN7Twkq0DGm3ZJvQabz
- nodeId: 0:1（主 Frame `1:20`「上传简历」，1920×1080）
- 账号权限：Starter Plan + View Seat（对目标文件仅 `can view`）

## 结论

**Figma REST API 可以读取该只读共享文件**，设计数据与素材已全部提取并结构化。
之前 MCP 失败的原因是 MCP 要求编辑权限，REST API 只读端点不受此限制。
Token 要求：`file_content:read` scope。

## 目录结构

```text
figma-data/
├── raw/                                    # 原始 API 响应（未做任何修改）
│   ├── file_D0jjN7Twkq0DGm3ZJvQabz_depth2.json   # GET /v1/files?depth=2
│   ├── node_1_20_full.json                       # GET /v1/files/.../nodes?ids=1:20
│   ├── export-images_svg_response.json           # GET /v1/images?...&format=svg
│   └── export-images_png_response.json           # GET /v1/images?...&format=png
├── processed/
│   ├── design-tree.json                    # 前端友好的节点树（含相对坐标、完整样式）
│   ├── design-tokens.json                  # 颜色 / 字体 / 圆角 / 效果 token 及使用位置
│   └── asset-map.json                      # 节点 ID → 素材文件映射
├── assets/
│   ├── svg/                                # 9 个矢量素材（图标 + 步骤指示圆点）
│   └── images/                             # 1 张插画 PNG（2x，1526×1138）
├── scripts/
│   ├── extract_design.py                   # raw → design-tree + design-tokens（可重跑）
│   └── fetch_assets.py                     # 下载素材 + 生成 asset-map（幂等，复用已有文件）
└── figma-access-status.json                # 访问验证记录
```

## design-tree.json 节点属性覆盖

每个节点包含：id、name、type、visible、绝对坐标 + 相对父级坐标（box.relativeX/Y）、
Auto Layout（本设计未使用，字段缺省）、constraints、fills/strokes/background（含 hex 与 RGBA）、
opacity/blendMode、圆角（含四角独立半径）、描边（粗细/对齐/虚线）、effects、
文本（字体族/字号/字重/行高/字距/对齐/完整文案/填充色）、矢量标记、
exportSettings、boundVariables、interactions，
以及完整原始节点 `raw`（未解释的字段一律保留，不丢弃）。

## design-tokens.json 统计

- 颜色：14 个（含使用节点位置），如 `#0538BB`（主蓝边框）、`#75ACFF`（主按钮）、`#F8FBF9`（页面背景）
- 字体：6 组（Inter Regular/Medium 11–40px、Alibaba PuHuiTi Medium 40px，含行高/字距）
- 圆角：4 档（2 / 8 / 15 / 32 px）
- 效果：2 条（NODE 可见，见文件）

## 素材清单（asset-map.json）

- SVG ×9：上传云图标、3 组步骤圆点（外圈+内圈）、2 个对勾图标
- PNG ×1：简历场景插画（节点 `1:21`，2x）
- 全部通过官方 `/v1/images` 接口批量导出（2 次 API 调用），已本地化，下游工具无需再消耗 API 额度

## 质量检查结果（全部通过）

1. 节点解析 26/26，无遗漏；
2. 文本 7/7 节点文案与原始 JSON 完全一致（共 244 字符）；
3. 坐标、尺寸、字体、颜色与原始 JSON 逐项比对无差异；
4. 素材 10/10 下载成功且格式校验通过（SVG 含 `<svg` 根元素、PNG 魔数正确）；
5. 本目录所有数据均为 API 真实返回或由其直接转换，无推断数据。

## 已知限制 / 未提取内容

- `boundVariables`：主按钮颜色绑定了设计变量，但变量集合（名称/语义）未提取；
  所有颜色均有具体 RGBA 值，不影响还原。
- 页面 Frame 的 `exportSettings` 为整页 JPG 4x，按要求未导出整页截图作为替代方案。
- 插画原始 imageRef（`f3b98a45...`）可用 `GET /v1/files/{key}/images` 获取原图，当前 2x PNG 已够用。

## 使用建议

- 前端还原时以 `processed/design-tree.json` 为主输入，`design-tokens.json` 提炼样式常量，`asset-map.json` 引用素材；
- 重新生成：`python scripts/extract_design.py && python scripts/fetch_assets.py`（素材已存在时自动复用）；
- 凭据不存储在本目录，Token 只保存在用户环境变量 `FIGMA_TOKEN`。
