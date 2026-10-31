export const labels = { normal: '正常留言', spam: '垃圾信息' }
export const reviewStatuses = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
export const predictionStatuses = {
  pending: '待预测', no_features: '无有效特征', no_model: '模型未就绪', error: '预测失败',
}

export function formatTime(value) {
  if (!value) return ''
  // 后端旧数据可能没有时区，统一按 UTC 解释，再显示北京时间。
  let normalized = value
  if (!/(Z|[+-]\d{2}:?\d{2})$/i.test(value)) normalized += 'Z'
  return new Date(normalized).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai', hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}
