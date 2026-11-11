'use client';
import {ResponsiveContainer,AreaChart,Area,CartesianGrid,XAxis,YAxis,Tooltip,BarChart,Bar,Cell,PieChart,Pie,Legend} from 'recharts';
import {Trend} from '../lib/api';
const COLORS=['#7465e8','#22b89a','#f6ae64','#e9798e','#5ca6e8'];
const tick={fontSize:11,fill:'#8e92a8'};
export function RevenueChart({data}:{data:Trend[]}){
 const d=data.filter((_,i)=>i%Math.max(1,Math.floor(data.length/18))===0);
 return <div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={d} margin={{top:8,right:8,bottom:0,left:-18}}><defs><linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7668ec" stopOpacity={.25}/><stop offset="100%" stopColor="#7668ec" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#eeeef5" vertical={false} strokeDasharray="4 4"/><XAxis dataKey="date" tickFormatter={(x)=>x.slice(5)} tick={tick} axisLine={false} tickLine={false}/><YAxis tick={tick} tickFormatter={v=>v>=1000?`${(v/1000).toFixed(0)}k`:v} axisLine={false} tickLine={false}/><Tooltip contentStyle={{borderRadius:12,border:'1px solid #ededf4',fontSize:12}} formatter={(v)=>`₹${Number(v).toLocaleString('en-IN')}`}/><Area dataKey="revenue" type="monotone" stroke="#7465e8" fill="url(#revenueFill)" strokeWidth={3}/><Area dataKey="profit" type="monotone" stroke="#22b89a" fill="none" strokeWidth={2}/></AreaChart></ResponsiveContainer></div>
}
export function CategoryChart({data}:{data:{name:string;revenue:number}[]}){
 return <div className="chart smallchart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} layout="vertical" margin={{top:0,right:12,left:12,bottom:0}}><XAxis type="number" tick={tick} tickFormatter={v=>`${Math.round(v/1000)}k`} axisLine={false} tickLine={false}/><YAxis type="category" dataKey="name" tick={{...tick,fontSize:10}} axisLine={false} tickLine={false} width={85}/><Tooltip formatter={v=>`₹${Number(v).toLocaleString('en-IN')}`} contentStyle={{borderRadius:10,fontSize:12}}/><Bar dataKey="revenue" radius={[0,6,6,0]} barSize={16}>{data.map((_,i)=><Cell key={i} fill={COLORS[i%COLORS.length]}/>)}</Bar></BarChart></ResponsiveContainer></div>
}
export function ReturnsChart({data}:{data:{name:string;count:number}[]}){
 return <div className="chart donut"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data} dataKey="count" nameKey="name" cx="50%" cy="50%" innerRadius={57} outerRadius={82} paddingAngle={3} stroke="none">{data.map((_,i)=><Cell key={i} fill={COLORS[i%COLORS.length]}/>)}</Pie><Tooltip contentStyle={{borderRadius:10,fontSize:12}}/><Legend verticalAlign="bottom" iconType="circle" iconSize={7} wrapperStyle={{fontSize:10,lineHeight:'20px'}}/></PieChart></ResponsiveContainer></div>
}
