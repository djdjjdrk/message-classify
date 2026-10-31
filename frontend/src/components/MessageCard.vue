<script setup>
import { formatTime, reviewStatuses } from '../utils/format.js'
defineProps({ message: Object })
</script>

<template>
  <article class="message-card">
    <div class="message-meta">
      <span>#{{ message.id }}<template v-if="message.author_nickname"> · {{ message.author_nickname }}</template></span>
      <span v-if="message.review_status" class="badge" :class="message.review_status">
        {{ reviewStatuses[message.review_status] }}
      </span>
      <time>{{ formatTime(message.created_at) }}</time>
    </div>
    <p class="message-content">{{ message.content }}</p>
    <slot />
  </article>
</template>
