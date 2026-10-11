import { Drawer } from './Dialog';
export type PaidRequest = { title: string; description: string; execute: () => void; };
export function ProviderAuthorization({ request, onClose }: { request: PaidRequest | null; onClose: () => void }) {
  return <Drawer open={!!request} onOpenChange={open => !open && onClose()} title="模型调用费用授权"><div className="drawer-body"><h3>{request?.title}</h3><p>{request?.description}</p><p>该操作会调用真实 Provider 并消耗 Token。缺少可核实计价依据，预计金额无法估算；授权仅限此操作，不自动执行下一轮、D Sandbox 或发布。</p><button className="primary" onClick={() => { const execute = request?.execute; onClose(); execute?.(); }}>授权并运行此操作</button><button className="secondary" onClick={onClose}>取消</button></div></Drawer>;
}
