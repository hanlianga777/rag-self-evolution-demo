// Presentation only. A saved Final label never establishes semantic support.
type SavedSource = { chunk_id?: string; parent_chunk_id?: string; matched_child_ids?: string[]; document?: string; document_name?: string; page_start?: number; page_end?: number; parent_page_start?: number; parent_page_end?: number };
export function answerCitationDisplay(text: string, final: SavedSource[]) {
  const labels = new Map<string, Set<string>>();
  for (const source of final) {
    const document = source.document || source.document_name;
    if (!document) continue;
    for (const id of [source.chunk_id,source.parent_chunk_id,...(source.matched_child_ids || [])]) {
      if (!id) continue;
      const parent=id === source.parent_chunk_id || id !== source.chunk_id;
      const start=parent ? source.parent_page_start ?? source.page_start : source.page_start;
      const end=parent ? source.parent_page_end ?? source.page_end : source.page_end;
      const location=[document, start != null ? `第${start}${end != null && end !== start ? `—${end}` : ''}页` : ''].filter(Boolean).join(' · ');
      const values=labels.get(id) || new Set<string>();values.add(location);labels.set(id,values);
    }
  }
  let unverified=0, changed=false;
  const displayed=text.replace(/\[(DOC-\d+-[CP]-\d+)(?:\s*[|｜][^\]\n]*)?\]|【(DOC-\d+-[CP]-\d+)(?:\s*[|｜][^】\n]*)?】/g, (_whole, square: string, corner: string) => {
    changed=true;const values=labels.get(square || corner);
    if (values?.size === 1) return `[${[...values][0]}]`;
    unverified++;return '[引用来源未核验]';
  });
  return {text:displayed,unverified,changed};
}
