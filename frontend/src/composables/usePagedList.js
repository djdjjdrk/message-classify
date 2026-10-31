import { computed, onScopeDispose, ref, toValue, watch } from 'vue'

export function usePagedList(fetchPage, filters = ref({})) {
  const items = ref([])
  const page = ref(1)
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  const pageSize = 10
  const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
  let revision = 0

  async function reload() {
    const current = ++revision
    loading.value = true
    error.value = ''
    try {
      const result = await toValue(fetchPage)({ page: page.value, page_size: pageSize, ...toValue(filters) })
      if (current !== revision) return
      total.value = result.total
      if (page.value > pages.value) {
        page.value = pages.value
        return
      }
      items.value = result.list
    } catch (failure) {
      if (current === revision) {
        items.value = []
        error.value = failure.message
      }
    } finally {
      if (current === revision) loading.value = false
    }
  }

  // 筛选条件改变后回到第一页；批量侦听只请求最终条件。
  watch([fetchPage, filters], () => { page.value = 1 }, { flush: 'sync' })
  watch([fetchPage, filters, page], reload, { immediate: true })
  onScopeDispose(() => { revision++ })
  return { items, page, total, pages, loading, error, reload }
}
