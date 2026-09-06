import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

import App from './App.vue'
import router from './router'

// 注册 echarts 必要组件
use([CanvasRenderer, PieChart, TitleComponent, TooltipComponent, LegendComponent])

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.component('VChart', VChart)

app.mount('#app')
