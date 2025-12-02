<template>
  <div class="flex flex-col p-8 h-screen items-center">
    <div class="w-full max-w-md rounded-lg flex-3 select-none">
      <Card class="h-auto">
        <CardHeader>
          <CardTitle
            class="text-6xl text-center font-bold text-transparent bg-clip-text bg-linear-to-br from-blue-500 via-purple-500 to-pink-500"
            >{{ profile?.max_floor ?? 0 }}</CardTitle
          >
        </CardHeader>
        <CardContent>
          <p class="text-lg text-center">最高层数</p>
        </CardContent>
      </Card>
    </div>
    <div class="w-full max-w-md flex-1 flex flex-col justify-center gap-4">
      <Button
        variant="outline"
        class="w-full text-md h-12"
        @click="$router.push({ name: 'combat' })"
      >
        开始闯塔
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useUserProfileStore } from '@/stores/userProfile'
import { onMounted } from 'vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { storeToRefs } from 'pinia'

const userProfileStore = useUserProfileStore()
const { profile } = storeToRefs(userProfileStore)

onMounted(() => {
  userProfileStore.getProfile()
})
</script>
