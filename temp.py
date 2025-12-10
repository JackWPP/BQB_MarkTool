import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体为SimHei，确保中文正常显示
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示为方块的问题

# 优化前后关键财务指标对比（单位：万元）
metrics = {
    '指标': ['储蓄率', '应急资金', '购房首付', '装修负债', '保险预算', '年化收益', '负债率'],
    '优化前': [28.1, 12.0, 30.0, 50.0, 3.0, 3.5, 96.1],
    '优化后': [35.0, 8.0, 40.0, 20.0, 5.5, 5.2, 62.3]
}

x = np.arange(len(metrics['指标']))
width = 0.35

fig, ax = plt.subplots(figsize=(12, 6))
bars1 = ax.bar(x - width/2, metrics['优化前'], width, label='优化前', color='#FF9999', alpha=0.8)
bars2 = ax.bar(x + width/2, metrics['优化后'], width, label='优化后', color='#66B2FF', alpha=0.8)

# 在柱状图上标注数值
def add_value_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')

add_value_labels(bars1)
add_value_labels(bars2)

ax.set_xlabel('财务健康指标', fontsize=12, fontweight='bold')
ax.set_ylabel('数值（%，或万元）', fontsize=12, fontweight='bold')
ax.set_title('2031年家庭理财方案优化前后对比', fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(metrics['指标'], rotation=15)
ax.legend(loc='upper right', fontsize=11)

# 添加优化效果说明文本
plt.figtext(0.5, 0.01, 
            "核心优化：储蓄率↑24% | 负债率↓35% | 保险保障↑83% | 年化收益↑49%\n"
            "实现路径：压缩弹性支出15.6万→10万 | 装修贷50万→20万 | 首付30%→40%",
            ha="center", fontsize=10, style='italic',
            bbox={"facecolor":"lightgrey", "alpha":0.5, "pad":5})

plt.tight_layout()
plt.show()