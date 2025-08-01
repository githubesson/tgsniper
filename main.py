import asyncio
import time
import json
import aiohttp
from telethon.sync import TelegramClient
from telethon import functions
from telethon.tl.types import InputPeerUser
from telethon.tl.tlobject import TLObject
from config import config

class InputInvoiceStarGiftResale(TLObject):
    CONSTRUCTOR_ID = 0xc39f5324

    def __init__(self, slug, to_id, ton: bool = False):
        super().__init__()
        self.slug = slug
        self.to_id = to_id
        # New flag for TON purchases per Telegram v6.0 resale changes
        self.ton = ton

    def _bytes(self):
        # Serialize according to Telegram TL schema for InputInvoiceStarGiftResale
        # flags: bit 0 -> ton
        result = self.CONSTRUCTOR_ID.to_bytes(4, 'little', signed=False)
        flags = (1 << 0) if self.ton else 0
        result += flags.to_bytes(4, 'little', signed=False)
        result += TLObject.serialize_bytes(self.slug)
        result += self.to_id.to_bytes()
        return result

async def send_discord_notification(webhook_url, gift_info, profit_percentage, profit_amount, total_spent, total_bought):
    if not webhook_url or webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        return
    
    try:
        embed = {
            "title": "🎯 Gift Sniped Successfully!",
            "color": 0x00ff00,
            "fields": [
                {
                    "name": "🎁 Gift Type",
                    "value": gift_info.get('gift_type', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "💰 Purchase Price",
                    "value": f"{gift_info.get('price', 0)} {'TON' if gift_info.get('currency') == 'TON' else '⭐'}",
                    "inline": True
                },
                {
                    "name": "📈 Profit Potential",
                    "value": f"{profit_percentage:.1f}% ({profit_amount} {'TON' if gift_info.get('currency') == 'TON' else '⭐'})",
                    "inline": True
                },
                {
                    "name": "🆔 Gift ID",
                    "value": str(gift_info.get('gift_id', 'Unknown')),
                    "inline": True
                },
                {
                    "name": "📊 Session Stats",
                    "value": f"{total_bought} bought • {total_spent} {'TON' if gift_info.get('currency') == 'TON' else '⭐'} spent",
                    "inline": True
                },
                {
                    "name": "⏰ Time",
                    "value": time.strftime('%H:%M:%S'),
                    "inline": True
                }
            ],
            "footer": {
                "text": "TG Star Gift Sniper"
            },
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
        }
        
        payload = {
            "embeds": [embed]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status == 204:
                    print(f"  📨 Discord notification sent successfully")
                else:
                    print(f"  ❌ Discord notification failed: {response.status}")
                    
    except Exception as e:
        print(f"  ❌ Discord notification error: {e}")


async def send_discord_summary(webhook_url, scan_count, total_resale, opportunities_found, scan_duration):
    if not webhook_url or webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        return
    
    try:
        embed = {
            "title": "📊 Market Scan Summary",
            "color": 0x0099ff,
            "fields": [
                {
                    "name": "🔍 Scan #",
                    "value": str(scan_count),
                    "inline": True
                },
                {
                    "name": "📦 Total Resale Gifts",
                    "value": str(total_resale),
                    "inline": True
                },
                {
                    "name": "💎 Profitable Opportunities",
                    "value": str(opportunities_found),
                    "inline": True
                },
                {
                    "name": "⏱️ Scan Duration",
                    "value": f"{scan_duration:.1f}s",
                    "inline": True
                },
                {
                    "name": "⏰ Time",
                    "value": time.strftime('%H:%M:%S'),
                    "inline": True
                }
            ],
            "footer": {
                "text": "Market Scanner"
            }
        }
        
        payload = {
            "embeds": [embed]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status != 204:
                    print(f"  ❌ Discord summary failed: {response.status}")
                    
    except Exception as e:
        print(f"  ❌ Discord summary error: {e}")


async def get_all_star_gifts(client):
    try:
        result = await client(functions.payments.GetStarGiftsRequest(hash=0))
        return result.gifts if hasattr(result, 'gifts') else []
    except Exception as e:
        print(f"Error fetching star gifts: {e}")
        return []


async def get_resale_gifts_for_gift_id(client, gift_id, gift_index=None, total_gifts=None, min_price=None):
    """
    Returns a list of normalized resale entries (dicts), each representing
    a price point in a specific currency for a given gift.
    Dict schema:
      {
        'gift': original_tl_object,
        'gift_id': int,
        'gift_type': str,
        'slug': str,
        'currency': 'STARS' | 'TON',
        'price': int|float,
        'resale_ton_only': bool,
      }
    """
    try:
        result = await client(functions.payments.GetResaleStarGiftsRequest(
            gift_id=gift_id,
            offset="",
            limit=100
        ))
        
        resale_gifts = result.gifts if hasattr(result, 'gifts') else []

        normalized = []
        for g in resale_gifts:
            # Defaults and safe getters
            title = getattr(g, 'title', 'Unknown')
            slug = getattr(g, 'slug', None)
            gift_id_val = getattr(g, 'id', gift_id)
            resale_ton_only = getattr(g, 'resale_ton_only', False)

            # New pricing container: resale_amount (list of objects)
            # Each entry may contain starsAmount or starsTonAmount
            amounts = getattr(g, 'resale_amount', None)

            # Backward compatibility: some objects may still expose resell_stars
            legacy_stars = getattr(g, 'resell_stars', None)

            stars_prices = []
            ton_prices = []

            if amounts and isinstance(amounts, (list, tuple)):
                for amt in amounts:
                    # Telethon TL objects expose attributes; fallback via getattr
                    starsAmount = getattr(amt, 'starsAmount', None)
                    starsTonAmount = getattr(amt, 'starsTonAmount', None)
                    if starsAmount is not None:
                        stars_prices.append(int(starsAmount))
                    if starsTonAmount is not None:
                        try:
                            ton_prices.append(float(starsTonAmount))
                        except Exception:
                            pass

            # Fallback to legacy
            if legacy_stars is not None and not stars_prices:
                try:
                    stars_prices.append(int(legacy_stars))
                except Exception:
                    pass

            # Create normalized entries per currency
            for sp in stars_prices:
                normalized.append({
                    'gift': g,
                    'gift_id': gift_id_val,
                    'gift_type': title,
                    'slug': slug,
                    'currency': 'STARS',
                    'price': sp,
                    'resale_ton_only': resale_ton_only
                })

            for tp in ton_prices:
                normalized.append({
                    'gift': g,
                    'gift_id': gift_id_val,
                    'gift_type': title,
                    'slug': slug,
                    'currency': 'TON',
                    'price': tp,
                    'resale_ton_only': resale_ton_only
                })

        # Apply floor filter only for Stars market, consistent with previous logic
        if min_price:
            stars_entries = [e for e in normalized if e['currency'] == 'STARS']
            filtered_for_floor = [e for e in stars_entries if not (120 <= e['price'] <= 140)]
            if filtered_for_floor:
                try:
                    floor_price = min(e['price'] for e in filtered_for_floor)
                    if floor_price < min_price:
                        return []
                except ValueError:
                    pass

        return normalized
    except Exception as e:
        return []


def calculate_profit_opportunities(entries, min_profit_pct_stars, min_profit_pct_ton):
    """
    entries: list of normalized dicts from scanner
    Returns list of opportunities sorted by profit pct desc, then price asc.
    Each opportunity:
      {
        'entry': buy_entry_dict,
        'profit_percentage': float,
        'profit_amount': float,
        'lowest_price': float,
        'second_price': float,
        'gift_type': str,
        'currency': 'STARS'|'TON'
      }
    """
    # Group by (gift_type, currency)
    by_group = {}
    for e in entries:
        key = (e['gift_type'], e['currency'])
        by_group.setdefault(key, []).append(e)

    opportunities = []

    for (gift_type, currency), group in by_group.items():
        if len(group) < 2:
            continue
        # Sort by price in that currency
        group_sorted = sorted(group, key=lambda x: x['price'])
        lowest = group_sorted[0]
        second = group_sorted[1]
        lowest_price = float(lowest['price'])
        second_price = float(second['price'])
        profit_amount = second_price - lowest_price
        profit_pct = (profit_amount / lowest_price) * 100 if lowest_price > 0 else 0.0

        if currency == 'STARS':
            if profit_pct >= min_profit_pct_stars:
                opportunities.append({
                    'entry': lowest,
                    'profit_percentage': profit_pct,
                    'profit_amount': profit_amount,
                    'lowest_price': lowest_price,
                    'second_price': second_price,
                    'gift_type': gift_type,
                    'currency': currency
                })
        else:  # TON
            if config.ENABLE_TON_SNIPING and profit_pct >= min_profit_pct_ton:
                opportunities.append({
                    'entry': lowest,
                    'profit_percentage': profit_pct,
                    'profit_amount': profit_amount,
                    'lowest_price': lowest_price,
                    'second_price': second_price,
                    'gift_type': gift_type,
                    'currency': currency
                })

    opportunities.sort(key=lambda x: (-x['profit_percentage'], x['lowest_price']))
    return opportunities


# Legacy helper not used anymore in TON-aware flow; kept for compatibility if needed.
def group_gifts_by_type(_):
    return {}


async def scan_all_resale_gifts_concurrent(client, all_gifts, batch_size=50, min_price=None):
    all_resale_gifts = []
    skipped_collections = 0
    
    print(f"🔍 Scanning {len(all_gifts)} gifts for resale listings (concurrent batches of {batch_size})...")
    if min_price:
        print(f"🚫 Skipping collections with floor price < {min_price} stars")
    
    for batch_start in range(0, len(all_gifts), batch_size):
        batch_end = min(batch_start + batch_size, len(all_gifts))
        batch_gifts = all_gifts[batch_start:batch_end]
        
        print(f"  🚀 Processing batch {batch_start//batch_size + 1}/{(len(all_gifts) + batch_size - 1)//batch_size} ({len(batch_gifts)} gifts)...")
        
        tasks = []
        for i, gift in enumerate(batch_gifts):
            task = get_resale_gifts_for_gift_id(
                client, 
                gift.id, 
                batch_start + i, 
                len(all_gifts),
                min_price
            )
            tasks.append(task)
        
        try:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            batch_gifts_with_resale = 0
            for result in batch_results:
                if isinstance(result, list):
                    # result is already normalized entries per gift (could be empty)
                    if result:
                        all_resale_gifts.extend(result)
                        batch_gifts_with_resale += 1
                elif isinstance(result, Exception):
                    pass
            
            skipped_in_batch = len(batch_gifts) - batch_gifts_with_resale
            skipped_collections += skipped_in_batch
            
            print(f"  ✅ Batch completed: {batch_gifts_with_resale} gifts had qualifying resale items, {skipped_in_batch} skipped")
            
        except Exception as e:
            print(f"  ❌ Batch error: {e}")
        
        if batch_end < len(all_gifts):
            await asyncio.sleep(0.1)
    
    print(f"✅ Concurrent scan complete: Found {len(all_resale_gifts)} qualifying resale entries")
    print(f"🚫 Skipped {skipped_collections} collections (floor price too low or no resale)")
    return all_resale_gifts


async def scan_all_resale_gifts_sequential(client, all_gifts, min_price=None):
    all_resale_gifts = []
    skipped_collections = 0
    
    print(f"🔍 Scanning {len(all_gifts)} gifts for resale listings (sequential fallback)...")
    if min_price:
        print(f"🚫 Skipping collections with floor price < {min_price} stars")
    
    for i, gift in enumerate(all_gifts):
        try:
            gift_id = gift.id
            resale_entries = await get_resale_gifts_for_gift_id(client, gift_id, i, len(all_gifts), min_price)
            
            if resale_entries:
                all_resale_gifts.extend(resale_entries)
            else:
                skipped_collections += 1
            
            if i % 10 == 0 and i > 0:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"  ❌ Error checking gift {gift_id}: {e}")
            skipped_collections += 1
            continue
    
    print(f"✅ Sequential scan complete: Found {len(all_resale_gifts)} qualifying resale entries")
    print(f"🚫 Skipped {skipped_collections} collections (floor price too low or no resale)")
    return all_resale_gifts


async def snipe_gifts_in_range_with_profit(
    client,
    entries,
    min_price=140,
    max_price=170,
    min_profit_percentage=10,
    webhook_url=None
):
    """
    entries: normalized entries list from scan functions
    Applies price windows per currency and computes opportunities per currency.
    """
    # Split by currency and apply filters
    stars_entries = [e for e in entries if e['currency'] == 'STARS' and min_price <= e['price'] <= max_price]

    ton_entries = []
    if config.ENABLE_TON_SNIPING:
        ton_entries = [e for e in entries if e['currency'] == 'TON' and config.MIN_TON_PRICE <= e['price'] <= config.MAX_TON_PRICE]
        # If seller set resale_ton_only and we had a STARS mirror entry, that’s okay since we separated by currency.

    filtered = stars_entries + ton_entries
    if not filtered:
        return 0, 0, []

    print(f"💰 Analyzing profit margins (per-currency). Stars: {len(stars_entries)}, TON: {len(ton_entries)}")

    opportunities = calculate_profit_opportunities(
        filtered,
        min_profit_pct_stars=min_profit_percentage,
        min_profit_pct_ton=config.MIN_TON_PROFIT_PERCENTAGE
    )

    if not opportunities:
        print(f"📉 No entries meet minimum profit margins (Stars ≥ {min_profit_percentage}%, TON ≥ {config.MIN_TON_PROFIT_PERCENTAGE}%)")
        return 0, 0, []

    print(f"🎯 Found {len(opportunities)} profitable opportunities!")

    bought_count = 0
    total_spent_stars = 0.0
    total_spent_ton = 0.0

    for op in opportunities:
        entry = op['entry']
        currency = op['currency']
        gift = entry['gift']
        gift_type = entry['gift_type']
        buy_price = entry['lowest_price']
        profit_pct = op['profit_percentage']
        profit_amount = op['profit_amount']

        try:
            price_label = f"{buy_price} {'TON' if currency == 'TON' else '⭐'}"
            print(f"🎯 SNIPING: {price_label} | Profit: {profit_pct:.1f}% ({profit_amount} {'TON' if currency == 'TON' else '⭐'}) | Type: {gift_type}")

            me = await client.get_me()

            invoice = InputInvoiceStarGiftResale(
                slug=getattr(gift, 'slug', entry.get('slug')),
                to_id=InputPeerUser(user_id=me.id, access_hash=me.access_hash),
                ton=(currency == 'TON')
            )

            payment_form = await client(functions.payments.GetPaymentFormRequest(
                invoice=invoice
            ))

            # For TON, Telegram API uses same entry point but the invoice carries ton=True
            payment_result = await client(functions.payments.SendStarsFormRequest(
                form_id=payment_form.form_id,
                invoice=invoice
            ))

            if payment_result:
                bought_count += 1
                if currency == 'TON':
                    total_spent_ton += buy_price
                else:
                    total_spent_stars += buy_price

                print(f"✅ SNIPED! Bought for {price_label} (potential profit: {profit_pct:.1f}% / {profit_amount} {'TON' if currency == 'TON' else '⭐'})")

                gift_info = {
                    'gift_type': gift_type,
                    'price': buy_price,
                    'gift_id': entry.get('gift_id', getattr(gift, 'id', None)),
                    'currency': currency
                }

                # For session stats in notification, show same-currency spent
                spent_for_currency = total_spent_ton if currency == 'TON' else total_spent_stars

                await send_discord_notification(webhook_url, gift_info, profit_pct, profit_amount, spent_for_currency, bought_count)
            else:
                print(f"❌ Purchase failed - no result")

        except Exception as e:
            error_msg = str(e)
            if "GIFT_NOT_AVAILABLE" in error_msg or "ALREADY_SOLD" in error_msg:
                print(f"⚡ Too slow - gift already sold")
            elif "INSUFFICIENT_FUNDS" in error_msg:
                if currency == 'TON':
                    print(f"💸 Insufficient TON balance")
                else:
                    print(f"💸 Insufficient stars balance")
            else:
                print(f"❌ Purchase error: {error_msg}")

    # Return totals in stars terms for backward compatibility; TON total separate print
    if total_spent_ton > 0:
        print(f"💠 TON spent this run: {total_spent_ton}")
    return bought_count, int(total_spent_stars), opportunities


async def continuous_sniper(client, min_price, max_price, min_profit_percentage, use_concurrent, batch_size, webhook_url):
    print(f"🚀 Starting continuous gift sniper with profit analysis")
    print(f"💰 Target range: {min_price}-{max_price} stars")
    print(f"💠 TON sniping: {'ENABLED' if config.ENABLE_TON_SNIPING else 'DISABLED'}", flush=True)
    if config.ENABLE_TON_SNIPING:
        print(f"   └─ TON price range: {config.MIN_TON_PRICE}-{config.MAX_TON_PRICE} TON")
        print(f"   └─ TON min profit: {config.MIN_TON_PROFIT_PERCENTAGE}%")
    print(f"📈 Minimum profit margin: {min_profit_percentage}% (Stars)")
    print(f"🚫 Floor price filter: Skip collections < {min_price} stars")
    print(f"⚡ Concurrent scanning: {'ON' if use_concurrent else 'OFF'}")
    if use_concurrent:
        print(f"📦 Batch size: {batch_size}")
    if webhook_url and webhook_url != "YOUR_DISCORD_WEBHOOK_URL_HERE":
        print(f"📨 Discord notifications: ENABLED")
    else:
        print(f"📨 Discord notifications: DISABLED (configure DISCORD_WEBHOOK_URL)")
    print(f"⏱️  Checking every {config.SCAN_INTERVAL} second(s)")
    print("-" * 60)
    
    print("📋 Fetching all available star gifts...")
    all_gifts = await get_all_star_gifts(client)
    
    if not all_gifts:
        print("❌ No star gifts found. Exiting.")
        return
    
    print(f"📦 Found {len(all_gifts)} total star gifts")
    
    with open('all_gifts.json', 'w') as f:
        gift_data = []
        for gift in all_gifts:
            gift_info = {
                'id': gift.id,
                'title': getattr(gift, 'title', 'Unknown'),
                'stars': getattr(gift, 'stars', 0)
            }
            gift_data.append(gift_info)
        json.dump(gift_data, f, indent=2)
    print("💾 Saved gift info to all_gifts.json")
    
    total_bought = 0
    total_spent = 0
    scan_count = 0
    
    while True:
        try:
            scan_start = time.time()
            scan_count += 1
            
            print(f"\n🔄 Scan #{scan_count} - {time.strftime('%H:%M:%S')}")
            
            if use_concurrent:
                all_resale_gifts = await scan_all_resale_gifts_concurrent(client, all_gifts, batch_size, min_price)
            else:
                all_resale_gifts = await scan_all_resale_gifts_sequential(client, all_gifts, min_price)
            
            if all_resale_gifts:
                bought, spent, opportunities = await snipe_gifts_in_range_with_profit(
                    client, all_resale_gifts, min_price, max_price, min_profit_percentage, webhook_url
                )
                
                print(f"📊 Found {len(all_resale_gifts)} qualifying resale entries, {len(opportunities)} profitable opportunities")
                
                if scan_count % config.SUMMARY_INTERVAL == 0:
                    await send_discord_summary(webhook_url, scan_count, len(all_resale_gifts), len(opportunities), time.time() - scan_start)
                
                if bought > 0:
                    total_bought += bought
                    total_spent += spent
                    print(f"🎉 Session stats: {total_bought} bought, {total_spent} stars spent")
                elif opportunities:
                    print(f"⏳ Found opportunities but couldn't complete purchases")
                else:
                    print(f"📉 No profitable opportunities found")
            else:
                print(f"📭 No qualifying resale gifts found")
            
            scan_duration = time.time() - scan_start
            print(f"⏱️  Scan completed in {scan_duration:.2f}s")
            
            sleep_time = max(0, config.SCAN_INTERVAL - scan_duration)
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                print(f"⚠️  Scan took longer than {config.SCAN_INTERVAL}s interval")
                
        except KeyboardInterrupt:
            print(f"\n🛑 Stopping sniper...")
            print(f"📈 Final stats: {total_bought} gifts bought, {total_spent} stars spent")
            break
        except Exception as e:
            print(f"💥 Error in monitoring loop: {e}")
            await asyncio.sleep(config.SCAN_INTERVAL)


async def main():
    async with TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH) as client:
        await continuous_sniper(
            client, 
            config.MIN_PRICE, 
            config.MAX_PRICE, 
            config.MIN_PROFIT_PERCENTAGE, 
            config.USE_CONCURRENT, 
            config.BATCH_SIZE, 
            config.DISCORD_WEBHOOK_URL
        )


if __name__ == "__main__":
    asyncio.run(main())