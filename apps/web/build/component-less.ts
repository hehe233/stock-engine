import { readFile } from 'node:fs/promises';
import { isAbsolute, resolve } from 'node:path';
import { normalizePath, type Plugin } from 'vite';

// Keep source filenames familiar while using Vite's native Less/CSS Modules pipeline.
export function componentLess(): Plugin {
  let sourceRoot = '';
  const sources = new Map<string, string>();
  return {
    name: 'stock-engine-component-less',
    enforce: 'pre',
    configResolved(config) {
      sourceRoot = normalizePath(resolve(config.root, 'src')) + '/';
    },
    async resolveId(source, importer) {
      if (!importer || source.includes('?') || source.includes('#')) return;
      if (!source.endsWith('/index.less') || (!source.startsWith('.') && !isAbsolute(source))) {
        return;
      }
      const resolved = await this.resolve(source, importer, { skipSelf: true });
      if (!resolved || resolved.external) return;
      const file = normalizePath(resolved.id);
      if (!file.startsWith(sourceRoot) || file.includes('/node_modules/')) return;
      // The virtual file stays next to its source, preserving Less imports and asset URLs.
      const id = file.slice(0, -5) + '.module.less';
      sources.set(id, file);
      return id;
    },
    async load(id) {
      const file = sources.get(id);
      if (!file) return;
      this.addWatchFile(file);
      return readFile(file, 'utf8');
    },
    handleHotUpdate(context) {
      const changed = normalizePath(context.file);
      const modules = new Set(context.modules);
      for (const [id, file] of sources) {
        if (file !== changed) continue;
        const module = context.server.moduleGraph.getModuleById(id);
        if (module) modules.add(module);
      }
      return [...modules];
    },
  };
}
