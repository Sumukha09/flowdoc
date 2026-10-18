const SUPPORTED_EXTENSIONS = new Set(['.pdf', '.txt']);

export const SUPPORTED_DOCUMENT_ACCEPT = '.pdf,.txt';

export function stageSupportedDocuments(fileList) {
  const supported = [];
  const unsupported = [];

  for (const file of Array.from(fileList)) {
    const extension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
    if (!SUPPORTED_EXTENSIONS.has(extension)) {
      unsupported.push(file.name);
      continue;
    }

    supported.push({
      id: Math.random().toString(36).substr(2, 9),
      name: file.name,
      object: file,
    });
  }

  return { supported, unsupported };
}
