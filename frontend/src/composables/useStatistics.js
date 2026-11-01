import { onScopeDispose, ref } from 'vue'
import { getStatistics } from '../api/statistics.js'

export function useStatistics(fetchStatistics = getStatistics) {
  const statistics = ref(null)
  const loading = ref(false)
  const error = ref('')
  let revision = 0

  async function reload() {
    const current = ++revision
    loading.value = true
    error.value = ''
    try {
      const result = await fetchStatistics()
      if (current === revision) statistics.value = result
    } catch (failure) {
      if (current === revision) error.value = failure.message
    } finally {
      if (current === revision) loading.value = false
    }
  }

  reload()
  onScopeDispose(() => { revision++ })
  return { statistics, loading, error, reload }
}
