import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { gzipSync } from 'node:zlib';
import type { Plugin } from 'vite';

// Local diagnostics only: rendered module sizes are pre-minification estimates.
export function bundleReport(reportPath: string): Plugin {
  let root = '';
  return {
    name: 'stock-bundle-report',
    apply: 'build',
    configResolved(config) {
      root = config.root;
    },
    // Vite adds preload dependencies during generateBundle; measure the final output.
    writeBundle(_, bundle) {
      const chunks = Object.values(bundle)
        .filter((output) => output.type === 'chunk')
        .map((chunk) => ({
          file: chunk.fileName,
          isEntry: chunk.isEntry,
          imports: chunk.imports,
          dynamicImports: chunk.dynamicImports,
          bytes: Buffer.byteLength(chunk.code),
          gzipBytes: gzipSync(chunk.code).length,
          modules: Object.entries(chunk.modules)
            .filter(([, module]) => module.renderedLength > 0)
            .map(([id, module]) => ({
              id: relative(root, id).replaceAll('\\', '/'),
              renderedLength: module.renderedLength,
            }))
            .sort((a, b) => b.renderedLength - a.renderedLength),
        }));
      const byFile = new Map(chunks.map((chunk) => [chunk.file, chunk]));
      const entrypoints = chunks
        .filter((chunk) => chunk.isEntry)
        .map((entry) => {
          const files = new Set<string>();
          const visit = (file: string) => {
            const chunk = byFile.get(file);
            if (!chunk || files.has(file)) return;
            files.add(file);
            chunk.imports.forEach(visit);
          };
          visit(entry.file);
          const dependencies = [...files].map((file) => byFile.get(file)!);
          return {
            entry: entry.file,
            files: [...files],
            bytes: dependencies.reduce((total, chunk) => total + chunk.bytes, 0),
            gzipBytes: dependencies.reduce((total, chunk) => total + chunk.gzipBytes, 0),
          };
        });
      const destination = resolve(root, reportPath);
      mkdirSync(dirname(destination), { recursive: true });
      writeFileSync(destination, JSON.stringify({ entrypoints, chunks }, null, 2));
    },
  };
}
