import { createApp, lakebase, server } from '@databricks/appkit';
import { setupConsoleRoutes } from './routes/console-routes';

createApp({
  plugins: [
    lakebase(),
    server(),
  ],
  onPluginsReady(appkit) {
    setupConsoleRoutes(appkit);
  },
}).catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
