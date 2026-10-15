import { createApp } from "vue"
import { setConfig } from "frappe-ui"
import App from "./App.vue"
import router from "./router"
import { loadDevBoot, sysdefaults } from "./boot"
import "./style.css"

async function start() {
	await loadDevBoot()
	setConfig("systemTimezone", sysdefaults().time_zone)
	createApp(App).use(router).mount("#app")
}

start()
