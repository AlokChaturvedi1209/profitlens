export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export type Kpis = {orders:number;gross_revenue:number;net_revenue:number;profit:number;refunds:number;margin:number;return_rate:number;avg_order_value:number;returns:number};
export type Trend = {date:string;revenue:number;profit:number;refunds:number;orders:number;returns:number};
export type ProductStat = {sku:string;name:string;category:string;revenue:number;profit:number;orders:number;returns:number;return_rate:number};
export type Overview = {kpis:Kpis;trend:Trend[];products:ProductStat[];categories:{name:string;revenue:number;profit:number}[];reasons:{name:string;count:number}[];statuses:{name:string;count:number}[]};
export type Workspace = {id:number;name:string;is_demo:boolean};
export type OrderRow = {id:string;date:string;product:string;sku:string;qty:number;revenue:number;status:string;profit:number};
export type AlertRow = {id:number;title:string;description:string;kind:string;severity:string;acknowledged:boolean;date:string};
export type InventoryRow = {sku:string;name:string;category:string;cost:number;price:number;stock:number;low_stock:boolean};
export type ReturnRow = {id:string;order:string;product:string;reason:string;refund:number;date:string;restockable:boolean};
export type User = {id:number;name:string;email:string};
export async function request<T>(path:string,token?:string|null,init?:RequestInit):Promise<T>{
 const headers = new Headers(init?.headers||{});
 if(token)headers.set('Authorization',`Bearer ${token}`);
 if(init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type'))headers.set('Content-Type','application/json');
 let r:Response;
 try {r=await fetch(`${API}${path}`,{...init,headers,cache:'no-store'});}
 catch {throw new Error('Cannot reach API. Check that the backend is running on port 8000.');}
 if(!r.ok){const v=await r.json().catch(()=>({detail:`Request failed (${r.status})`}));throw new Error(typeof v.detail==='string'?v.detail:JSON.stringify(v.detail));}
 return r.json() as Promise<T>;
}
export const rupee=(v:number)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(v);
export const compact=(v:number)=>new Intl.NumberFormat('en-IN',{notation:'compact',maximumFractionDigits:1}).format(v);
export const shortDate=(s:string)=>new Date(s).toLocaleDateString('en-IN',{day:'2-digit',month:'short'});
