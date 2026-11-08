import App from './App.svelte'
import 'leaflet/dist/leaflet.css'

const target = document.getElementById('app')
if (!target) throw new Error('Missing #app mount point')

new App({ target })
