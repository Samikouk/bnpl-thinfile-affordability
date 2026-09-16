import { createApp, lakebase, server } from '@databricks/appkit';
import { setupConsoleRoutes } from './routes/console-routes';

createApp({
  plugins: [
    lakebase(),
    server(),
  ],
  async onPluginsReady(appkit) {
    await setupConsoleRoutes(appkit);
  },
}).catch(console.error);
