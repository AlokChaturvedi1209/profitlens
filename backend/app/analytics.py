"""Financial measures and robust anomaly heuristics. All amounts in INR."""
from __future__ import annotations
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from .core import Order, Product, Return, Alert


def money(value: float) -> float: return round(value + 1e-8, 2)

def order_financials(o: Order, ret: Return | None = None) -> dict:
    gross = o.quantity * o.unit_price
    cogs = o.quantity * o.unit_cost
    refund = ret.refunded_amount if ret else 0
    costs = cogs + o.shipping + o.platform_fee + (ret.return_shipping if ret else 0)
    # Conservative: returned goods' cost is not automatically recovered; restocking does not imply a sale.
    return {'revenue': gross, 'refund': refund, 'net_revenue': gross-refund, 'costs': costs,
            'profit': gross-refund-costs, 'quantity': o.quantity}

def scoped_data(db: Session, workspace_id: int, start: datetime | None = None, end: datetime | None = None):
    stmt = select(Order).options(joinedload(Order.product)).where(Order.workspace_id == workspace_id, Order.status != 'cancelled')
    if start: stmt = stmt.where(Order.purchased_at >= start)
    if end: stmt = stmt.where(Order.purchased_at < end)
    orders = db.scalars(stmt.order_by(Order.purchased_at.asc())).all()
    ids = [o.id for o in orders]
    returns = db.scalars(select(Return).where(Return.workspace_id == workspace_id, Return.order_id.in_(ids))).all() if ids else []
    ret_map = {r.order_id: r for r in returns}
    return orders, ret_map

def overview(db: Session, workspace_id: int, days: int = 90) -> dict:
    now = datetime.utcnow()
    start = (now-timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    orders, ret_map = scoped_data(db, workspace_id, start)
    sums = defaultdict(float); daily = defaultdict(lambda: defaultdict(float)); product_totals = defaultdict(lambda: defaultdict(float))
    categories = defaultdict(lambda: defaultdict(float)); reasons = Counter(); statuses = Counter(); returned = 0
    for o in orders:
        r = ret_map.get(o.id)
        vals = order_financials(o, r)
        day = o.purchased_at.date().isoformat()
        p = product_totals[o.product.sku]
        p['sku'] = o.product.sku; p['name'] = o.product.name; p['category'] = o.product.category
        cat = categories[o.product.category]
        for key in ['revenue', 'refund', 'net_revenue', 'costs', 'profit', 'quantity']:
            sums[key] += vals[key]; daily[day][key] += vals[key]; p[key] += vals[key]; cat[key] += vals[key]
        p['orders'] += 1; daily[day]['orders'] += 1; statuses[o.status] += 1
        if r:
            returned += 1; reasons[r.reason] += 1; p['returns'] += 1; daily[day]['returns'] += 1
    count = len(orders)
    trend=[]
    for i in range(days+1):
        day = (start + timedelta(days=i)).date().isoformat()
        if day > now.date().isoformat(): break
        t=daily[day]
        trend.append({'date':day, 'revenue':money(t['revenue']), 'profit':money(t['profit']),
                      'refunds':money(t['refund']), 'orders':int(t['orders']), 'returns':int(t['returns'])})
    top = sorted(({'sku':x['sku'], 'name':x['name'], 'category':x['category'],
                   'revenue':money(x['revenue']), 'profit':money(x['profit']),
                   'orders':int(x['orders']), 'returns':int(x['returns']),
                   'return_rate':round(100*x['returns']/x['orders'],1)} for x in product_totals.values()),key=lambda v:v['revenue'],reverse=True)
    return {'kpis':{'orders':count,'gross_revenue':money(sums['revenue']), 'net_revenue':money(sums['net_revenue']),
                    'profit':money(sums['profit']), 'refunds':money(sums['refund']),
                    'margin':round(100*sums['profit']/sums['net_revenue'],1) if sums['net_revenue'] else 0,
                    'return_rate':round(100*returned/count,1) if count else 0,
                    'avg_order_value':money(sums['revenue']/count) if count else 0,
                    'returns':returned},
            'trend':trend, 'products':top,
            'categories':[{'name':k,'revenue':money(v['revenue']),'profit':money(v['profit'])} for k,v in categories.items()],
            'reasons':[{'name':k,'count':v} for k,v in reasons.most_common()],
            'statuses':[{'name':k,'count':v} for k,v in statuses.items()]}

def detect_alerts(db: Session, workspace_id: int, *, notify: bool = False) -> list[Alert]:
    """Upserts one alert per product or recent sales window; notification only on first creation."""
    from .mailer import send_alert_email
    report = overview(db, workspace_id, 30)
    new = []
    def create(key,kind,severity,title,description):
        if db.scalar(select(Alert).where(Alert.workspace_id == workspace_id, Alert.alert_key == key)): return
        alert = Alert(workspace_id=workspace_id, alert_key=key,kind=kind,severity=severity,title=title,description=description)
        db.add(alert); new.append(alert)
    for p in report['products']:
        if p['orders'] >= 8 and p['return_rate'] >= 20:
            create('returns:'+p['sku'],'high_returns','critical',f'High return rate: {p["name"]}',f'{p["return_rate"]}% of {p["orders"]} orders were returned in the past 30 days.')
        if p['orders'] >= 5 and p['profit'] < 0:
            create('loss:'+p['sku'],'negative_profit','warning',f'Loss-making product: {p["name"]}',f'Product produced ₹{abs(p["profit"]):,.0f} in losses over the past 30 days.')
    trend = report['trend']
    # Compare completed days only; require meaningful activity in baseline.
    if len(trend) >= 15:
        completed = trend[:-1]
        recent = completed[-3:]; baseline = completed[-14:-3]
        if len(recent)==3 and len(baseline)>=7:
            recent_avg = sum(v['revenue'] for v in recent)/3
            baseline_avg = sum(v['revenue'] for v in baseline)/len(baseline)
            if baseline_avg >= 1000 and recent_avg < baseline_avg * .55:
                create('revenue-drop:'+recent[-1]['date'],'revenue_drop','critical','Revenue dropped sharply',f'Average daily revenue fell {100*(1-recent_avg/baseline_avg):.0f}% against the previous 11-day baseline.')
    db.commit()
    if notify:
        for a in new: send_alert_email(a.title,a.description)
    return new
