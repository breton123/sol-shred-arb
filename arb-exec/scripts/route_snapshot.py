"""Restricted coherent-account quote adapter for the existing DLMM/Pump models.

One RPC account response is the input boundary. No acquisition, signing or sends.
Model applicability is separate from deployed-model and landing certification.
"""
import base64
from dataclasses import fields
import hashlib
from pathlib import Path
import struct
import sys

CAP = Path(__file__).resolve().parents[2]/"arb-cap"
for directory in (CAP, CAP/"timer_decay", CAP/"pump012", CAP/"dlmm_orders"):
    sys.path.insert(0,str(directory))
import record_dlmm as wire
import dlmm_quote as q
import pump_fee
import inventory
from solders.pubkey import Pubkey

CLOCK = "SysvarC1ock11111111111111111111111111111111"
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SYSVAR = "Sysvar1111111111111111111111111111111111111"


def raw(account, owner=None):
    if not account or (owner and account.get("owner") != owner):
        raise ValueError("missing_or_wrong_owner")
    return base64.b64decode(account['data'][0],validate=True)


def pk(data):
    return str(Pubkey.from_bytes(data))


def token_data(account, mint=False):
    data=raw(account)
    base=82 if mint else 165
    if account['owner'] not in (TOKEN,TOKEN22) or len(data)<base:
        raise ValueError('invalid_token_account')
    if data[45 if mint else 108] != 1:
        raise ValueError('token_uninitialized_or_frozen')
    if account['owner']==TOKEN:
        if len(data)!=base: raise ValueError('legacy_token_length')
        return data,[]
    if len(data)==base:return data,[]
    if len(data)<166 or data[165]!=(1 if mint else 2) or (mint and any(data[82:165])):
        raise ValueError('invalid_extension_header')
    types=[];offset=166
    allowed={18,19} if mint else {7}  # MetadataPointer/TokenMetadata; ImmutableOwner.
    while offset<len(data) and any(data[offset:]):
        if offset+4>len(data):raise ValueError('truncated_extension')
        kind,length=struct.unpack_from('<HH',data,offset);offset+=4
        if kind not in allowed or kind in types or offset+length>len(data):
            raise ValueError('unsupported_or_malformed_extension')
        if kind==7 and length!=0:raise ValueError('immutable_owner_length')
        types.append(kind);offset+=length
    return data,types


def quote_snapshot(accounts, slot, dp_fixture, bin_keys):
    roles={a['role']:a['pubkey'] for a in dp_fixture['hops'][1]['accounts']}
    dk=dp_fixture['keys'];pair=dk[9]
    clock=raw(accounts[CLOCK],SYSVAR)
    if len(clock)!=40 or struct.unpack_from('<Q',clock)[0]!=slot:
        raise ValueError('clock_context_mismatch')
    now=struct.unpack_from('<q',clock,32)[0]
    lbraw=raw(accounts[pair],wire.DLMM);lb=wire.parse_lbpair(lbraw)
    if lb['collect_fee_mode'] not in (0,1) or lb['status']!=0:
        raise ValueError('unsupported_dlmm_mode')
    if (pk(lb['token_x']),pk(lb['token_y']),pk(lb['vault_x']),pk(lb['vault_y'])) != (dk[15],dk[16],dk[11],dk[12]):
        raise ValueError('dlmm_topology_changed')
    poolraw=raw(accounts[roles['pool']],pump_fee.PUMP_AMM)
    if poolraw[:8]!=hashlib.sha256(b'account:Pool').digest()[:8]:raise ValueError('pump_discriminator')
    pool=pump_fee.parse_pool_meta(poolraw)
    if (pool['base_mint'],pool['quote_mint'])!=(dk[15],dk[16]) or pool['quote_mint']!=pump_fee.WSOL:
        raise ValueError('route_mint_mismatch')
    if pool['mayhem'] or pool['cashback'] or pool['holder']:raise ValueError('unsupported_pump_mode')
    if pk(poolraw[139:171])!=roles['pool_base_vault'] or pk(poolraw[171:203])!=roles['pool_quote_vault']:
        raise ValueError('pump_vault_topology_changed')
    mint_data={};extensions={}
    for key in (dk[15],dk[16]):
        mint_data[key],extensions[key]=token_data(accounts[key],True)
    amounts={}
    for key,mint,authority in [(dk[1],dk[16],dk[0]),(dk[2],dk[15],dk[0]),
             (dk[11],dk[15],pair),(dk[12],dk[16],pair),
             (roles['pool_base_vault'],dk[15],roles['pool']),
             (roles['pool_quote_vault'],dk[16],roles['pool'])]:
        data,extensions[key]=token_data(accounts[key])
        if pk(data[:32])!=mint or pk(data[32:64])!=authority or accounts[key]['owner']!=accounts[mint]['owner']:
            raise ValueError('token_topology_mismatch')
        amounts[key]=int.from_bytes(data[64:72],'little')
    bins={}
    for index,key in bin_keys.items():
        data=raw(accounts[key],wire.DLMM)
        if data[:8]!=wire.BINARR_DISC or struct.unpack_from('<q',data,8)[0]!=index or pk(data[24:56])!=pair:
            raise ValueError('invalid_bin_array_identity')
        parsed=inventory.parse_bin_array(data)
        if len(parsed)!=70:raise ValueError('truncated_bins')
        if any(b['open_order_amount'] or b['processed_order_remaining_amount'] for b in parsed):
            raise ValueError('unsupported_limit_order_inventory')
        bins[index]=[q.Bin(b['id'],b['amount_x'],b['amount_y'],b['price']) for b in parsed]
    active=lb['active_id']//70
    if any(i not in bins for i in (active-1,active,active+1)):
        raise ValueError('active_bin_moved_outside_discovery')
    globraw=raw(accounts[roles['global_config']],pump_fee.PUMP_AMM)
    feeraw=raw(accounts[roles['fee_config']],pump_fee.PFEE)
    for data,name in [(globraw,'GlobalConfig'),(feeraw,'FeeConfig')]:
        if data[:8]!=hashlib.sha256(('account:'+name).encode()).digest()[:8]:raise ValueError('config_discriminator')
    glob=pump_fee.parse_global_config(globraw);fee=pump_fee.parse_fee_config(feeraw)
    rb=amounts[roles['pool_base_vault']];rq=amounts[roles['pool_quote_vault']]
    fees=pump_fee.resolve_fee_state(fee,glob,pool,int.from_bytes(mint_data[dk[15]][36:44],'little'),rb,rq,gate='coin_creator')
    if fees['buyback_bps']>10000:raise ValueError('invalid_protocol_fee_carve')
    pump=q.Pump(rb,rq,pool['virtual_quote_reserves'],fees['lp_fee_bps'],fees['protocol_fee_bps'],fees['creator_fee_bps'],glob['disable_flags'],0)
    params={f.name:lb[f.name] for f in fields(q.Dlmm) if f.name in lb}
    params.update(reserve_x=amounts[dk[11]],reserve_y=amounts[dk[12]],now_ts=now)
    dlmm={direction:q.Dlmm(**params,bins=bins[active]+bins[active+(1 if direction=='dp' else -1)]) for direction in ('dp','pd')}
    return {'dlmm':dlmm,'pump':pump,'fees':fees,'extensions':extensions,'inventory':amounts[dk[1]],'now':now,'active_array':active}


def quote_sizes(state,sizes):
    rows=[]
    for direction in ('dp','pd'):
        for amount in sizes:
            if amount>state['inventory']:continue
            if direction=='dp':
                mid=q.quote_dlmm(state['dlmm'][direction],amount,False)
                out=q.quote_pump(state['pump'],mid,1) if mid is not None else None
                # Existing timer helper lacks the reserve-liability gate present in C.
                if mid is not None:
                    p=state['pump'];gross=(p.reserve_quote+p.virtual_quote)*mid//(p.reserve_base+mid)
                    lp=(gross*p.lp_fee_bps+9999)//10000
                    if gross-lp>p.reserve_quote:out=None
            else:
                mid=q.quote_pump(state['pump'],amount,0)
                out=q.quote_dlmm(state['dlmm'][direction],mid,True) if mid is not None else None
            rows.append({'direction':direction,'amount_in':amount,'intermediate':mid,'amount_out':out,
                         'gross':out-amount if out is not None else None,'model_quote_available':out is not None})
    return rows


def transient_cycle_amounts(value,user_quote,user_base,executor):
    """Simulation validation only; failed transactions do not commit these CPIs."""
    err=value.get('err')
    if err not in (None,{'InstructionError':[2,{'Custom':6}]}):return None
    logs=value.get('logs',[])
    for program in (wire.DLMM,pump_fee.PUMP_AMM):
        if f'Program {program} success' not in logs or any(s.startswith(f'Program {program} failed') for s in logs):return None
    if err and f'Program {executor} failed: custom program error: 0x6' not in logs:return None
    flow={user_quote:[0,0],user_base:[0,0]}
    n=0
    for group in value.get('innerInstructions',[]):
        for ix in group['instructions']:
            if ix.get('programId') not in (TOKEN,TOKEN22):continue
            parsed=ix.get('parsed',{})
            if parsed.get('type') not in ('transfer','transferChecked'):return None
            info=parsed.get('info',{})
            amount=int(info.get('amount',info.get('tokenAmount',{}).get('amount',-1)))
            if amount<0:return None
            n+=1
            if info.get('source') in flow:flow[info['source']][0]+=amount
            if info.get('destination') in flow:flow[info['destination']][1]+=amount
    quote_in,quote_out=flow[user_quote];base_out,base_in=flow[user_base]
    if not n or not quote_in or not base_in or base_in!=base_out:return None
    return {'amount_in':quote_in,'intermediate':base_in,'amount_out':quote_out,
            'gross_before_guard':quote_out-quote_in,'committed':err is None,
            'source':'complete parsed token transfers inside successful venue CPIs; simulation only'}
