# Evidence Card 模板

在正式写 report 之前，为每个重要 claim 创建一张 evidence card。

```markdown
### Evidence Card: <短名称>

- **Type**: contribution | motivation | method | formula | figure | experiment | limitation
- **Location**: section/page/paragraph/figure/table/equation
- **Paper text summary**: 论文原文关键句或段落大意
- **Concrete details**: 具体数据、符号、设置
- **Why it matters**: 为什么这个证据重要
- **Related report sections**: WHAT / WHY / HOW / EXPERIMENT / 创新点 / 局限性
- **Confidence**: high | medium | low
```

## 建卡顺序建议

1. 先读 Abstract + Introduction + Conclusion，建立 WHAT 和 WHY 的卡片。
2. 再读 Method/Approach 章节，建立 HOW 卡片（每个模块一张）。
3. 最后读 Experiments 章节，建立 EXPERIMENT 卡片（每个实验一张）。
4. 写报告时把卡片按 WHAT/WHY/HOW/EXPERIMENT 结构重新组织，而不是按论文章节平铺。

## 示例

```markdown
### Evidence Card: Task definition — price manipulation detection

- **Type**: motivation
- **Location**: Sec. 1, p. 2, "Price manipulation attacks..."
- **Paper text summary**: 作者指出现有工具主要检测代码级漏洞，无法识别协议级经济行为。
- **Concrete details**: 攻击者使用 flash loan 在单笔 transaction 内操纵 DEX 价格。
- **Why it matters**: 这是整篇论文的 motivation 起点。
- **Related report sections**: WHY · 背景问题 / 现有方法不足
- **Confidence**: high
```
