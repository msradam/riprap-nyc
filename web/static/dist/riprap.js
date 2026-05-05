const es = "5";
typeof window < "u" && ((window.__svelte ??= {}).v ??= /* @__PURE__ */ new Set()).add(es);
const ts = 1, rs = 2, ns = 16, ss = 1, is = 4, ls = 8, os = 16, as = 4, fs = 1, us = 2, Fr = "[", rr = "[!", $r = "[?", nr = "]", Ge = {}, P = Symbol(), zr = "http://www.w3.org/1999/xhtml", cs = "http://www.w3.org/2000/svg", hs = "http://www.w3.org/1998/Math/MathML", ds = !1;
var jr = Array.isArray, vs = Array.prototype.indexOf, rt = Array.prototype.includes, Ct = Array.from, At = Object.keys, gt = Object.defineProperty, qe = Object.getOwnPropertyDescriptor, ps = Object.getOwnPropertyDescriptors, _s = Object.prototype, gs = Array.prototype, Hr = Object.getPrototypeOf, kr = Object.isExtensible;
function bs(e) {
  return typeof e == "function";
}
const re = () => {
};
function ms(e) {
  for (var t = 0; t < e.length; t++)
    e[t]();
}
function qr() {
  var e, t, r = new Promise((n, s) => {
    e = n, t = s;
  });
  return { promise: r, resolve: e, reject: t };
}
function ws(e, t) {
  if (Array.isArray(e))
    return e;
  if (!(Symbol.iterator in e))
    return Array.from(e);
  const r = [];
  for (const n of e)
    if (r.push(n), r.length === t) break;
  return r;
}
const H = 2, nt = 4, Rt = 8, Br = 1 << 24, he = 16, de = 32, Ne = 64, Ht = 128, se = 512, D = 1024, z = 2048, _e = 4096, V = 8192, Z = 16384, Ce = 32768, qt = 1 << 25, Ke = 65536, Bt = 1 << 17, ys = 1 << 18, Xe = 1 << 19, $s = 1 << 20, Ee = 1 << 25, Je = 65536, Nt = 1 << 21, bt = 1 << 22, De = 1 << 23, vt = Symbol("$state"), Ur = Symbol("legacy props"), ye = new class extends Error {
  name = "StaleReactionError";
  message = "The reaction that called `getAbortSignal()` was re-run or destroyed";
}(), ks = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  !!globalThis.document?.contentType && /* @__PURE__ */ globalThis.document.contentType.includes("xml")
), Lt = 3, at = 8;
function Es(e) {
  throw new Error("https://svelte.dev/e/lifecycle_outside_component");
}
function xs() {
  throw new Error("https://svelte.dev/e/async_derived_orphan");
}
function Ts(e, t, r) {
  throw new Error("https://svelte.dev/e/each_key_duplicate");
}
function Ss(e) {
  throw new Error("https://svelte.dev/e/effect_in_teardown");
}
function As() {
  throw new Error("https://svelte.dev/e/effect_in_unowned_derived");
}
function Ns(e) {
  throw new Error("https://svelte.dev/e/effect_orphan");
}
function Os() {
  throw new Error("https://svelte.dev/e/effect_update_depth_exceeded");
}
function Ms() {
  throw new Error("https://svelte.dev/e/hydration_failed");
}
function Cs(e) {
  throw new Error("https://svelte.dev/e/props_invalid_value");
}
function Rs() {
  throw new Error("https://svelte.dev/e/state_descriptors_fixed");
}
function Ls() {
  throw new Error("https://svelte.dev/e/state_prototype_fixed");
}
function Is() {
  throw new Error("https://svelte.dev/e/state_unsafe_mutation");
}
function Ds() {
  throw new Error("https://svelte.dev/e/svelte_boundary_reset_onerror");
}
function Ps() {
  console.warn("https://svelte.dev/e/derived_inert");
}
function wt(e) {
  console.warn("https://svelte.dev/e/hydration_mismatch");
}
function Fs() {
  console.warn("https://svelte.dev/e/svelte_boundary_reset_noop");
}
let N = !1;
function xe(e) {
  N = e;
}
let x;
function j(e) {
  if (e === null)
    throw wt(), Ge;
  return x = e;
}
function st() {
  return j(/* @__PURE__ */ ve(x));
}
function F(e) {
  if (N) {
    if (/* @__PURE__ */ ve(x) !== null)
      throw wt(), Ge;
    x = e;
  }
}
function Vr(e = 1) {
  if (N) {
    for (var t = e, r = x; t--; )
      r = /** @type {TemplateNode} */
      /* @__PURE__ */ ve(r);
    x = r;
  }
}
function Ot(e = !0) {
  for (var t = 0, r = x; ; ) {
    if (r.nodeType === at) {
      var n = (
        /** @type {Comment} */
        r.data
      );
      if (n === nr) {
        if (t === 0) return r;
        t -= 1;
      } else (n === Fr || n === rr || // "[1", "[2", etc. for if blocks
      n[0] === "[" && !isNaN(Number(n.slice(1)))) && (t += 1);
    }
    var s = (
      /** @type {TemplateNode} */
      /* @__PURE__ */ ve(r)
    );
    e && r.remove(), r = s;
  }
}
function Yr(e) {
  if (!e || e.nodeType !== at)
    throw wt(), Ge;
  return (
    /** @type {Comment} */
    e.data
  );
}
function Wr(e) {
  return e === this.v;
}
function Gr(e, t) {
  return e != e ? t == t : e !== t || e !== null && typeof e == "object" || typeof e == "function";
}
function Kr(e) {
  return !Gr(e, this.v);
}
let zs = !1, G = null;
function it(e) {
  G = e;
}
function It(e, t = !1, r) {
  G = {
    p: G,
    i: !1,
    c: null,
    e: null,
    s: e,
    x: null,
    r: (
      /** @type {Effect} */
      y
    ),
    l: null
  };
}
function Dt(e) {
  var t = (
    /** @type {ComponentContext} */
    G
  ), r = t.e;
  if (r !== null) {
    t.e = null;
    for (var n of r)
      wn(n);
  }
  return e !== void 0 && (t.x = e), t.i = !0, G = t.p, e ?? /** @type {T} */
  {};
}
function Jr() {
  return !0;
}
let ze = [];
function Zr() {
  var e = ze;
  ze = [], ms(e);
}
function Pe(e) {
  if (ze.length === 0 && !pt) {
    var t = ze;
    queueMicrotask(() => {
      t === ze && Zr();
    });
  }
  ze.push(e);
}
function js() {
  for (; ze.length > 0; )
    Zr();
}
function Xr(e) {
  var t = y;
  if (t === null)
    return A.f |= De, e;
  if (!(t.f & Ce) && !(t.f & nt))
    throw e;
  Ie(e, t);
}
function Ie(e, t) {
  for (; t !== null; ) {
    if (t.f & Ht) {
      if (!(t.f & Ce))
        throw e;
      try {
        t.b.error(e);
        return;
      } catch (r) {
        e = r;
      }
    }
    t = t.parent;
  }
  throw e;
}
const Hs = -7169;
function R(e, t) {
  e.f = e.f & Hs | t;
}
function sr(e) {
  e.f & se || e.deps === null ? R(e, D) : R(e, _e);
}
function Qr(e) {
  if (e !== null)
    for (const t of e)
      !(t.f & H) || !(t.f & Je) || (t.f ^= Je, Qr(
        /** @type {Derived} */
        t.deps
      ));
}
function en(e, t, r) {
  e.f & z ? t.add(e) : e.f & _e && r.add(e), Qr(e.deps), R(e, D);
}
function tn(e, t, r) {
  if (e == null)
    return t(void 0), re;
  const n = ft(
    () => e.subscribe(
      t,
      // @ts-expect-error
      r
    )
  );
  return n.unsubscribe ? () => n.unsubscribe() : n;
}
const Qe = [];
function rn(e, t = re) {
  let r = null;
  const n = /* @__PURE__ */ new Set();
  function s(l) {
    if (Gr(e, l) && (e = l, r)) {
      const f = !Qe.length;
      for (const a of n)
        a[1](), Qe.push(a, e);
      if (f) {
        for (let a = 0; a < Qe.length; a += 2)
          Qe[a][0](Qe[a + 1]);
        Qe.length = 0;
      }
    }
  }
  function i(l) {
    s(l(
      /** @type {T} */
      e
    ));
  }
  function o(l, f = re) {
    const a = [l, f];
    return n.add(a), n.size === 1 && (r = t(s, i) || re), l(
      /** @type {T} */
      e
    ), () => {
      n.delete(a), n.size === 0 && r && (r(), r = null);
    };
  }
  return { set: s, update: i, subscribe: o };
}
function qs(e) {
  let t;
  return tn(e, (r) => t = r)(), t;
}
let kt = !1, Ut = Symbol();
function Vt(e, t, r) {
  const n = r[t] ??= {
    store: null,
    source: /* @__PURE__ */ ar(void 0),
    unsubscribe: re
  };
  if (n.store !== e && !(Ut in r))
    if (n.unsubscribe(), n.store = e ?? null, e == null)
      n.source.v = void 0, n.unsubscribe = re;
    else {
      var s = !0;
      n.unsubscribe = tn(e, (i) => {
        s ? n.source.v = i : te(n.source, i);
      }), s = !1;
    }
  return e && Ut in r ? qs(e) : b(n.source);
}
function nn() {
  const e = {};
  function t() {
    cr(() => {
      for (var r in e)
        e[r].unsubscribe();
      gt(e, Ut, {
        enumerable: !1,
        value: !0
      });
    });
  }
  return [e, t];
}
function Bs(e) {
  var t = kt;
  try {
    return kt = !1, [e(), kt];
  } finally {
    kt = t;
  }
}
const Fe = /* @__PURE__ */ new Set();
let S = null, ue = null, Yt = null, pt = !1, jt = !1, et = null, xt = null;
var Er = 0;
let Us = 1;
class Oe {
  id = Us++;
  /**
   * The current values of any signals that are updated in this batch.
   * Tuple format: [value, is_derived] (note: is_derived is false for deriveds, too, if they were overridden via assignment)
   * They keys of this map are identical to `this.#previous`
   * @type {Map<Value, [any, boolean]>}
   */
  current = /* @__PURE__ */ new Map();
  /**
   * The values of any signals (sources and deriveds) that are updated in this batch _before_ those updates took place.
   * They keys of this map are identical to `this.#current`
   * @type {Map<Value, any>}
   */
  previous = /* @__PURE__ */ new Map();
  /**
   * When the batch is committed (and the DOM is updated), we need to remove old branches
   * and append new ones by calling the functions added inside (if/each/key/etc) blocks
   * @type {Set<(batch: Batch) => void>}
   */
  #e = /* @__PURE__ */ new Set();
  /**
   * If a fork is discarded, we need to destroy any effects that are no longer needed
   * @type {Set<(batch: Batch) => void>}
   */
  #n = /* @__PURE__ */ new Set();
  /**
   * Callbacks that should run only when a fork is committed.
   * @type {Set<(batch: Batch) => void>}
   */
  #t = /* @__PURE__ */ new Set();
  /**
   * Async effects that are currently in flight
   * @type {Map<Effect, number>}
   */
  #i = /* @__PURE__ */ new Map();
  /**
   * Async effects that are currently in flight, _not_ inside a pending boundary
   * @type {Map<Effect, number>}
   */
  #s = /* @__PURE__ */ new Map();
  /**
   * A deferred that resolves when the batch is committed, used with `settled()`
   * TODO replace with Promise.withResolvers once supported widely enough
   * @type {{ promise: Promise<void>, resolve: (value?: any) => void, reject: (reason: unknown) => void } | null}
   */
  #l = null;
  /**
   * The root effects that need to be flushed
   * @type {Effect[]}
   */
  #r = [];
  /**
   * Effects created while this batch was active.
   * @type {Effect[]}
   */
  #o = [];
  /**
   * Deferred effects (which run after async work has completed) that are DIRTY
   * @type {Set<Effect>}
   */
  #f = /* @__PURE__ */ new Set();
  /**
   * Deferred effects that are MAYBE_DIRTY
   * @type {Set<Effect>}
   */
  #u = /* @__PURE__ */ new Set();
  /**
   * A map of branches that still exist, but will be destroyed when this batch
   * is committed — we skip over these during `process`.
   * The value contains child effects that were dirty/maybe_dirty before being reset,
   * so they can be rescheduled if the branch survives.
   * @type {Map<Effect, { d: Effect[], m: Effect[] }>}
   */
  #a = /* @__PURE__ */ new Map();
  /**
   * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
   * @type {Set<Effect>}
   */
  #h = /* @__PURE__ */ new Set();
  is_fork = !1;
  #v = !1;
  /** @type {Set<Batch>} */
  #d = /* @__PURE__ */ new Set();
  #c() {
    return this.is_fork || this.#s.size > 0;
  }
  #b() {
    for (const n of this.#d)
      for (const s of n.#s.keys()) {
        for (var t = !1, r = s; r.parent !== null; ) {
          if (this.#a.has(r)) {
            t = !0;
            break;
          }
          r = r.parent;
        }
        if (!t)
          return !0;
      }
    return !1;
  }
  /**
   * Add an effect to the #skipped_branches map and reset its children
   * @param {Effect} effect
   */
  skip_effect(t) {
    this.#a.has(t) || this.#a.set(t, { d: [], m: [] }), this.#h.delete(t);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(t, r = (n) => this.schedule(n)) {
    var n = this.#a.get(t);
    if (n) {
      this.#a.delete(t);
      for (var s of n.d)
        R(s, z), r(s);
      for (s of n.m)
        R(s, _e), r(s);
    }
    this.#h.add(t);
  }
  #p() {
    if (Er++ > 1e3 && (Fe.delete(this), Vs()), !this.#c()) {
      for (const l of this.#f)
        this.#u.delete(l), R(l, z), this.schedule(l);
      for (const l of this.#u)
        R(l, _e), this.schedule(l);
    }
    const t = this.#r;
    this.#r = [], this.apply();
    var r = et = [], n = [], s = xt = [];
    for (const l of t)
      try {
        this.#g(l, r, n);
      } catch (f) {
        throw on(l), f;
      }
    if (S = null, s.length > 0) {
      var i = Oe.ensure();
      for (const l of s)
        i.schedule(l);
    }
    if (et = null, xt = null, this.#c() || this.#b()) {
      this.#_(n), this.#_(r);
      for (const [l, f] of this.#a)
        ln(l, f);
    } else {
      this.#i.size === 0 && Fe.delete(this), this.#f.clear(), this.#u.clear();
      for (const l of this.#e) l(this);
      this.#e.clear(), xr(n), xr(r), this.#l?.resolve();
    }
    var o = (
      /** @type {Batch | null} */
      /** @type {unknown} */
      S
    );
    if (this.#r.length > 0) {
      const l = o ??= this;
      l.#r.push(...this.#r.filter((f) => !l.#r.includes(f)));
    }
    o !== null && (Fe.add(o), o.#p());
  }
  /**
   * Traverse the effect tree, executing effects or stashing
   * them for later execution as appropriate
   * @param {Effect} root
   * @param {Effect[]} effects
   * @param {Effect[]} render_effects
   */
  #g(t, r, n) {
    t.f ^= D;
    for (var s = t.first; s !== null; ) {
      var i = s.f, o = (i & (de | Ne)) !== 0, l = o && (i & D) !== 0, f = l || (i & V) !== 0 || this.#a.has(s);
      if (!f && s.fn !== null) {
        o ? s.f ^= D : i & nt ? r.push(s) : $t(s) && (i & he && this.#u.add(s), ot(s));
        var a = s.first;
        if (a !== null) {
          s = a;
          continue;
        }
      }
      for (; s !== null; ) {
        var u = s.next;
        if (u !== null) {
          s = u;
          break;
        }
        s = s.parent;
      }
    }
  }
  /**
   * @param {Effect[]} effects
   */
  #_(t) {
    for (var r = 0; r < t.length; r += 1)
      en(t[r], this.#f, this.#u);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(t, r, n = !1) {
    t.v !== P && !this.previous.has(t) && this.previous.set(t, t.v), t.f & De || (this.current.set(t, [r, n]), ue?.set(t, r)), this.is_fork || (t.v = r);
  }
  activate() {
    S = this;
  }
  deactivate() {
    S = null, ue = null;
  }
  flush() {
    try {
      jt = !0, S = this, this.#p();
    } finally {
      Er = 0, Yt = null, et = null, xt = null, jt = !1, S = null, ue = null, Be.clear();
    }
  }
  discard() {
    for (const t of this.#n) t(this);
    this.#n.clear(), this.#t.clear(), Fe.delete(this);
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(t) {
    this.#o.push(t);
  }
  #m() {
    for (const u of Fe) {
      var t = u.id < this.id, r = [];
      for (const [c, [d, v]] of this.current) {
        if (u.current.has(c)) {
          var n = (
            /** @type {[any, boolean]} */
            u.current.get(c)[0]
          );
          if (t && d !== n)
            u.current.set(c, [d, v]);
          else
            continue;
        }
        r.push(c);
      }
      var s = [...u.current.keys()].filter((c) => !this.current.has(c));
      if (s.length === 0)
        t && u.discard();
      else if (r.length > 0) {
        if (t)
          for (const c of this.#h)
            u.unskip_effect(c, (d) => {
              d.f & (he | bt) ? u.schedule(d) : u.#_([d]);
            });
        u.activate();
        var i = /* @__PURE__ */ new Set(), o = /* @__PURE__ */ new Map();
        for (var l of r)
          sn(l, s, i, o);
        o = /* @__PURE__ */ new Map();
        var f = [...u.current.keys()].filter(
          (c) => this.current.has(c) ? (
            /** @type {[any, boolean]} */
            this.current.get(c)[0] !== c
          ) : !0
        );
        for (const c of this.#o)
          !(c.f & (Z | V | Bt)) && ir(c, f, o) && (c.f & (bt | he) ? (R(c, z), u.schedule(c)) : u.#f.add(c));
        if (u.#r.length > 0) {
          u.apply();
          for (var a of u.#r)
            u.#g(a, [], []);
          u.#r = [];
        }
        u.deactivate();
      }
    }
    for (const u of Fe)
      u.#d.has(this) && (u.#d.delete(this), u.#d.size === 0 && !u.#c() && (u.activate(), u.#p()));
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  increment(t, r) {
    let n = this.#i.get(r) ?? 0;
    if (this.#i.set(r, n + 1), t) {
      let s = this.#s.get(r) ?? 0;
      this.#s.set(r, s + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   * @param {boolean} skip - whether to skip updates (because this is triggered by a stale reaction)
   */
  decrement(t, r, n) {
    let s = this.#i.get(r) ?? 0;
    if (s === 1 ? this.#i.delete(r) : this.#i.set(r, s - 1), t) {
      let i = this.#s.get(r) ?? 0;
      i === 1 ? this.#s.delete(r) : this.#s.set(r, i - 1);
    }
    this.#v || n || (this.#v = !0, Pe(() => {
      this.#v = !1, this.flush();
    }));
  }
  /**
   * @param {Set<Effect>} dirty_effects
   * @param {Set<Effect>} maybe_dirty_effects
   */
  transfer_effects(t, r) {
    for (const n of t)
      this.#f.add(n);
    for (const n of r)
      this.#u.add(n);
    t.clear(), r.clear();
  }
  /** @param {(batch: Batch) => void} fn */
  oncommit(t) {
    this.#e.add(t);
  }
  /** @param {(batch: Batch) => void} fn */
  ondiscard(t) {
    this.#n.add(t);
  }
  /** @param {(batch: Batch) => void} fn */
  on_fork_commit(t) {
    this.#t.add(t);
  }
  run_fork_commit_callbacks() {
    for (const t of this.#t) t(this);
    this.#t.clear();
  }
  settled() {
    return (this.#l ??= qr()).promise;
  }
  static ensure() {
    if (S === null) {
      const t = S = new Oe();
      jt || (Fe.add(S), pt || Pe(() => {
        S === t && t.flush();
      }));
    }
    return S;
  }
  apply() {
    {
      ue = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(t) {
    if (Yt = t, t.b?.is_pending && t.f & (nt | Rt | Br) && !(t.f & Ce)) {
      t.b.defer_effect(t);
      return;
    }
    for (var r = t; r.parent !== null; ) {
      r = r.parent;
      var n = r.f;
      if (et !== null && r === y && (A === null || !(A.f & H)))
        return;
      if (n & (Ne | de)) {
        if (!(n & D))
          return;
        r.f ^= D;
      }
    }
    this.#r.push(r);
  }
}
function Se(e) {
  var t = pt;
  pt = !0;
  try {
    for (var r; ; ) {
      if (js(), S === null)
        return (
          /** @type {T} */
          r
        );
      S.flush();
    }
  } finally {
    pt = t;
  }
}
function Vs() {
  try {
    Os();
  } catch (e) {
    Ie(e, Yt);
  }
}
let we = null;
function xr(e) {
  var t = e.length;
  if (t !== 0) {
    for (var r = 0; r < t; ) {
      var n = e[r++];
      if (!(n.f & (Z | V)) && $t(n) && (we = /* @__PURE__ */ new Set(), ot(n), n.deps === null && n.first === null && n.nodes === null && n.teardown === null && n.ac === null && kn(n), we?.size > 0)) {
        Be.clear();
        for (const s of we) {
          if (s.f & (Z | V)) continue;
          const i = [s];
          let o = s.parent;
          for (; o !== null; )
            we.has(o) && (we.delete(o), i.push(o)), o = o.parent;
          for (let l = i.length - 1; l >= 0; l--) {
            const f = i[l];
            f.f & (Z | V) || ot(f);
          }
        }
        we.clear();
      }
    }
    we = null;
  }
}
function sn(e, t, r, n) {
  if (!r.has(e) && (r.add(e), e.reactions !== null))
    for (const s of e.reactions) {
      const i = s.f;
      i & H ? sn(
        /** @type {Derived} */
        s,
        t,
        r,
        n
      ) : i & (bt | he) && !(i & z) && ir(s, t, n) && (R(s, z), lr(
        /** @type {Effect} */
        s
      ));
    }
}
function ir(e, t, r) {
  const n = r.get(e);
  if (n !== void 0) return n;
  if (e.deps !== null)
    for (const s of e.deps) {
      if (rt.call(t, s))
        return !0;
      if (s.f & H && ir(
        /** @type {Derived} */
        s,
        t,
        r
      ))
        return r.set(
          /** @type {Derived} */
          s,
          !0
        ), !0;
    }
  return r.set(e, !1), !1;
}
function lr(e) {
  S.schedule(e);
}
function ln(e, t) {
  if (!(e.f & de && e.f & D)) {
    e.f & z ? t.d.push(e) : e.f & _e && t.m.push(e), R(e, D);
    for (var r = e.first; r !== null; )
      ln(r, t), r = r.next;
  }
}
function on(e) {
  R(e, D);
  for (var t = e.first; t !== null; )
    on(t), t = t.next;
}
function Ys(e) {
  let t = 0, r = Ze(0), n;
  return () => {
    ur() && (b(r), dr(() => (t === 0 && (n = ft(() => e(() => _t(r)))), t += 1, () => {
      Pe(() => {
        t -= 1, t === 0 && (n?.(), n = void 0, _t(r));
      });
    })));
  };
}
var Ws = Ke | Xe;
function Gs(e, t, r, n) {
  new Ks(e, t, r, n);
}
class Ks {
  /** @type {Boundary | null} */
  parent;
  is_pending = !1;
  /**
   * API-level transformError transform function. Transforms errors before they reach the `failed` snippet.
   * Inherited from parent boundary, or defaults to identity.
   * @type {(error: unknown) => unknown}
   */
  transform_error;
  /** @type {TemplateNode} */
  #e;
  /** @type {TemplateNode | null} */
  #n = N ? x : null;
  /** @type {BoundaryProps} */
  #t;
  /** @type {((anchor: Node) => void)} */
  #i;
  /** @type {Effect} */
  #s;
  /** @type {Effect | null} */
  #l = null;
  /** @type {Effect | null} */
  #r = null;
  /** @type {Effect | null} */
  #o = null;
  /** @type {DocumentFragment | null} */
  #f = null;
  #u = 0;
  #a = 0;
  #h = !1;
  /** @type {Set<Effect>} */
  #v = /* @__PURE__ */ new Set();
  /** @type {Set<Effect>} */
  #d = /* @__PURE__ */ new Set();
  /**
   * A source containing the number of pending async deriveds/expressions.
   * Only created if `$effect.pending()` is used inside the boundary,
   * otherwise updating the source results in needless `Batch.ensure()`
   * calls followed by no-op flushes
   * @type {Source<number> | null}
   */
  #c = null;
  #b = Ys(() => (this.#c = Ze(this.#u), () => {
    this.#c = null;
  }));
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, r, n, s) {
    this.#e = t, this.#t = r, this.#i = (i) => {
      var o = (
        /** @type {Effect} */
        y
      );
      o.b = this, o.f |= Ht, n(i);
    }, this.parent = /** @type {Effect} */
    y.b, this.transform_error = s ?? this.parent?.transform_error ?? ((i) => i), this.#s = vr(() => {
      if (N) {
        const i = (
          /** @type {Comment} */
          this.#n
        );
        st();
        const o = i.data === rr;
        if (i.data.startsWith($r)) {
          const f = JSON.parse(i.data.slice($r.length));
          this.#g(f);
        } else o ? this.#_() : this.#p();
      } else
        this.#m();
    }, Ws), N && (this.#e = x);
  }
  #p() {
    try {
      this.#l = ee(() => this.#i(this.#e));
    } catch (t) {
      this.error(t);
    }
  }
  /**
   * @param {unknown} error The deserialized error from the server's hydration comment
   */
  #g(t) {
    const r = this.#t.failed;
    r && (this.#o = ee(() => {
      r(
        this.#e,
        () => t,
        () => () => {
        }
      );
    }));
  }
  #_() {
    const t = this.#t.pending;
    t && (this.is_pending = !0, this.#r = ee(() => t(this.#e)), Pe(() => {
      var r = this.#f = document.createDocumentFragment(), n = ie();
      r.append(n), this.#l = this.#y(() => ee(() => this.#i(n))), this.#a === 0 && (this.#e.before(r), this.#f = null, Ue(
        /** @type {Effect} */
        this.#r,
        () => {
          this.#r = null;
        }
      ), this.#w(
        /** @type {Batch} */
        S
      ));
    }));
  }
  #m() {
    try {
      if (this.is_pending = this.has_pending_snippet(), this.#a = 0, this.#u = 0, this.#l = ee(() => {
        this.#i(this.#e);
      }), this.#a > 0) {
        var t = this.#f = document.createDocumentFragment();
        gr(this.#l, t);
        const r = (
          /** @type {(anchor: Node) => void} */
          this.#t.pending
        );
        this.#r = ee(() => r(this.#e));
      } else
        this.#w(
          /** @type {Batch} */
          S
        );
    } catch (r) {
      this.error(r);
    }
  }
  /**
   * @param {Batch} batch
   */
  #w(t) {
    this.is_pending = !1, t.transfer_effects(this.#v, this.#d);
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    en(t, this.#v, this.#d);
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!this.#t.pending;
  }
  /**
   * @template T
   * @param {() => T} fn
   */
  #y(t) {
    var r = y, n = A, s = G;
    ge(this.#s), oe(this.#s), it(this.#s.ctx);
    try {
      return Oe.ensure(), t();
    } catch (i) {
      return Xr(i), null;
    } finally {
      ge(r), oe(n), it(s);
    }
  }
  /**
   * Updates the pending count associated with the currently visible pending snippet,
   * if any, such that we can replace the snippet with content once work is done
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  #$(t, r) {
    if (!this.has_pending_snippet()) {
      this.parent && this.parent.#$(t, r);
      return;
    }
    this.#a += t, this.#a === 0 && (this.#w(r), this.#r && Ue(this.#r, () => {
      this.#r = null;
    }), this.#f && (this.#e.before(this.#f), this.#f = null));
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, r) {
    this.#$(t, r), this.#u += t, !(!this.#c || this.#h) && (this.#h = !0, Pe(() => {
      this.#h = !1, this.#c && lt(this.#c, this.#u);
    }));
  }
  get_effect_pending() {
    return this.#b(), b(
      /** @type {Source<number>} */
      this.#c
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!this.#t.onerror && !this.#t.failed)
      throw t;
    S?.is_fork ? (this.#l && S.skip_effect(this.#l), this.#r && S.skip_effect(this.#r), this.#o && S.skip_effect(this.#o), S.on_fork_commit(() => {
      this.#k(t);
    })) : this.#k(t);
  }
  /**
   * @param {unknown} error
   */
  #k(t) {
    this.#l && (Y(this.#l), this.#l = null), this.#r && (Y(this.#r), this.#r = null), this.#o && (Y(this.#o), this.#o = null), N && (j(
      /** @type {TemplateNode} */
      this.#n
    ), Vr(), j(Ot()));
    var r = this.#t.onerror;
    let n = this.#t.failed;
    var s = !1, i = !1;
    const o = () => {
      if (s) {
        Fs();
        return;
      }
      s = !0, i && Ds(), this.#o !== null && Ue(this.#o, () => {
        this.#o = null;
      }), this.#y(() => {
        this.#m();
      });
    }, l = (f) => {
      try {
        i = !0, r?.(f, o), i = !1;
      } catch (a) {
        Ie(a, this.#s && this.#s.parent);
      }
      n && (this.#o = this.#y(() => {
        try {
          return ee(() => {
            var a = (
              /** @type {Effect} */
              y
            );
            a.b = this, a.f |= Ht, n(
              this.#e,
              () => f,
              () => o
            );
          });
        } catch (a) {
          return Ie(
            a,
            /** @type {Effect} */
            this.#s.parent
          ), null;
        }
      }));
    };
    Pe(() => {
      var f;
      try {
        f = this.transform_error(t);
      } catch (a) {
        Ie(a, this.#s && this.#s.parent);
        return;
      }
      f !== null && typeof f == "object" && typeof /** @type {any} */
      f.then == "function" ? f.then(
        l,
        /** @param {unknown} e */
        (a) => Ie(a, this.#s && this.#s.parent)
      ) : l(f);
    });
  }
}
function Js(e, t, r, n) {
  const s = Pt;
  var i = e.filter((d) => !d.settled);
  if (r.length === 0 && i.length === 0) {
    n(t.map(s));
    return;
  }
  var o = (
    /** @type {Effect} */
    y
  ), l = Zs(), f = i.length === 1 ? i[0].promise : i.length > 1 ? Promise.all(i.map((d) => d.promise)) : null;
  function a(d) {
    l();
    try {
      n(d);
    } catch (v) {
      o.f & Z || Ie(v, o);
    }
    Mt();
  }
  if (r.length === 0) {
    f.then(() => a(t.map(s)));
    return;
  }
  var u = an();
  function c() {
    Promise.all(r.map((d) => /* @__PURE__ */ Xs(d))).then((d) => a([...t.map(s), ...d])).catch((d) => Ie(d, o)).finally(() => u());
  }
  f ? f.then(() => {
    l(), c(), Mt();
  }) : c();
}
function Zs() {
  var e = (
    /** @type {Effect} */
    y
  ), t = A, r = G, n = (
    /** @type {Batch} */
    S
  );
  return function(i = !0) {
    ge(e), oe(t), it(r), i && !(e.f & Z) && (n?.activate(), n?.apply());
  };
}
function Mt(e = !0) {
  ge(null), oe(null), it(null), e && S?.deactivate();
}
function an() {
  var e = (
    /** @type {Effect} */
    y
  ), t = (
    /** @type {Boundary} */
    e.b
  ), r = (
    /** @type {Batch} */
    S
  ), n = t.is_rendered();
  return t.update_pending_count(1, r), r.increment(n, e), (s = !1) => {
    t.update_pending_count(-1, r), r.decrement(n, e, s);
  };
}
// @__NO_SIDE_EFFECTS__
function Pt(e) {
  var t = H | z;
  return y !== null && (y.f |= Xe), {
    ctx: G,
    deps: null,
    effects: null,
    equals: Wr,
    f: t,
    fn: e,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      P
    ),
    wv: 0,
    parent: y,
    ac: null
  };
}
// @__NO_SIDE_EFFECTS__
function Xs(e, t, r) {
  let n = (
    /** @type {Effect | null} */
    y
  );
  n === null && xs();
  var s = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), i = Ze(
    /** @type {V} */
    P
  ), o = !A, l = /* @__PURE__ */ new Map();
  return li(() => {
    var f = (
      /** @type {Effect} */
      y
    ), a = qr();
    s = a.promise;
    try {
      Promise.resolve(e()).then(a.resolve, a.reject).finally(Mt);
    } catch (v) {
      a.reject(v), Mt();
    }
    var u = (
      /** @type {Batch} */
      S
    );
    if (o) {
      if (f.f & Ce)
        var c = an();
      if (
        /** @type {Boundary} */
        n.b.is_rendered()
      )
        l.get(u)?.reject(ye), l.delete(u);
      else {
        for (const v of l.values())
          v.reject(ye);
        l.clear();
      }
      l.set(u, a);
    }
    const d = (v, h = void 0) => {
      if (c) {
        var p = h === ye;
        c(p);
      }
      if (!(h === ye || f.f & Z)) {
        if (u.activate(), h)
          i.f |= De, lt(i, h);
        else {
          i.f & De && (i.f ^= De), lt(i, v);
          for (const [_, $] of l) {
            if (l.delete(_), _ === u) break;
            $.reject(ye);
          }
        }
        u.deactivate();
      }
    };
    a.promise.then(d, (v) => d(null, v || "unknown"));
  }), cr(() => {
    for (const f of l.values())
      f.reject(ye);
  }), new Promise((f) => {
    function a(u) {
      function c() {
        u === s ? f(i) : a(s);
      }
      u.then(c, c);
    }
    a(s);
  });
}
// @__NO_SIDE_EFFECTS__
function Le(e) {
  const t = /* @__PURE__ */ Pt(e);
  return Tn(t), t;
}
// @__NO_SIDE_EFFECTS__
function fn(e) {
  const t = /* @__PURE__ */ Pt(e);
  return t.equals = Kr, t;
}
function Qs(e) {
  var t = e.effects;
  if (t !== null) {
    e.effects = null;
    for (var r = 0; r < t.length; r += 1)
      Y(
        /** @type {Effect} */
        t[r]
      );
  }
}
function or(e) {
  var t, r = y, n = e.parent;
  if (!Me && n !== null && n.f & (Z | V))
    return Ps(), e.v;
  ge(n);
  try {
    e.f &= ~Je, Qs(e), t = On(e);
  } finally {
    ge(r);
  }
  return t;
}
function un(e) {
  var t = or(e);
  if (!e.equals(t) && (e.wv = An(), (!S?.is_fork || e.deps === null) && (S !== null ? S.capture(e, t, !0) : e.v = t, e.deps === null))) {
    R(e, D);
    return;
  }
  Me || (ue !== null ? (ur() || S?.is_fork) && ue.set(e, t) : sr(e));
}
function ei(e) {
  if (e.effects !== null)
    for (const t of e.effects)
      (t.teardown || t.ac) && (t.teardown?.(), t.ac?.abort(ye), t.teardown = re, t.ac = null, mt(t, 0), pr(t));
}
function cn(e) {
  if (e.effects !== null)
    for (const t of e.effects)
      t.teardown && ot(t);
}
let Wt = /* @__PURE__ */ new Set();
const Be = /* @__PURE__ */ new Map();
let hn = !1;
function Ze(e, t) {
  var r = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: Wr,
    rv: 0,
    wv: 0
  };
  return r;
}
// @__NO_SIDE_EFFECTS__
function me(e, t) {
  const r = Ze(e);
  return Tn(r), r;
}
// @__NO_SIDE_EFFECTS__
function ar(e, t = !1, r = !0) {
  const n = Ze(e);
  return t || (n.equals = Kr), n;
}
function te(e, t, r = !1) {
  A !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!ce || A.f & Bt) && Jr() && A.f & (H | he | bt | Bt) && (le === null || !rt.call(le, e)) && Is();
  let n = r ? je(t) : t;
  return lt(e, n, xt);
}
function lt(e, t, r = null) {
  if (!e.equals(t)) {
    Be.set(e, Me ? t : e.v);
    var n = Oe.ensure();
    if (n.capture(e, t), e.f & H) {
      const s = (
        /** @type {Derived} */
        e
      );
      e.f & z && or(s), ue === null && sr(s);
    }
    e.wv = An(), dn(e, z, r), y !== null && y.f & D && !(y.f & (de | Ne)) && (Q === null ? ai([e]) : Q.push(e)), !n.is_fork && Wt.size > 0 && !hn && ti();
  }
  return t;
}
function ti() {
  hn = !1;
  for (const e of Wt)
    e.f & D && R(e, _e), $t(e) && ot(e);
  Wt.clear();
}
function _t(e) {
  te(e, e.v + 1);
}
function dn(e, t, r) {
  var n = e.reactions;
  if (n !== null)
    for (var s = n.length, i = 0; i < s; i++) {
      var o = n[i], l = o.f, f = (l & z) === 0;
      if (f && R(o, t), l & H) {
        var a = (
          /** @type {Derived} */
          o
        );
        ue?.delete(a), l & Je || (l & se && (y === null || !(y.f & Nt)) && (o.f |= Je), dn(a, _e, r));
      } else if (f) {
        var u = (
          /** @type {Effect} */
          o
        );
        l & he && we !== null && we.add(u), r !== null ? r.push(u) : lr(u);
      }
    }
}
function je(e) {
  if (typeof e != "object" || e === null || vt in e)
    return e;
  const t = Hr(e);
  if (t !== _s && t !== gs)
    return e;
  var r = /* @__PURE__ */ new Map(), n = jr(e), s = /* @__PURE__ */ me(0), i = Ve, o = (l) => {
    if (Ve === i)
      return l();
    var f = A, a = Ve;
    oe(null), Ar(i);
    var u = l();
    return oe(f), Ar(a), u;
  };
  return n && r.set("length", /* @__PURE__ */ me(
    /** @type {any[]} */
    e.length
  )), new Proxy(
    /** @type {any} */
    e,
    {
      defineProperty(l, f, a) {
        (!("value" in a) || a.configurable === !1 || a.enumerable === !1 || a.writable === !1) && Rs();
        var u = r.get(f);
        return u === void 0 ? o(() => {
          var c = /* @__PURE__ */ me(a.value);
          return r.set(f, c), c;
        }) : te(u, a.value, !0), !0;
      },
      deleteProperty(l, f) {
        var a = r.get(f);
        if (a === void 0) {
          if (f in l) {
            const u = o(() => /* @__PURE__ */ me(P));
            r.set(f, u), _t(s);
          }
        } else
          te(a, P), _t(s);
        return !0;
      },
      get(l, f, a) {
        if (f === vt)
          return e;
        var u = r.get(f), c = f in l;
        if (u === void 0 && (!c || qe(l, f)?.writable) && (u = o(() => {
          var v = je(c ? l[f] : P), h = /* @__PURE__ */ me(v);
          return h;
        }), r.set(f, u)), u !== void 0) {
          var d = b(u);
          return d === P ? void 0 : d;
        }
        return Reflect.get(l, f, a);
      },
      getOwnPropertyDescriptor(l, f) {
        var a = Reflect.getOwnPropertyDescriptor(l, f);
        if (a && "value" in a) {
          var u = r.get(f);
          u && (a.value = b(u));
        } else if (a === void 0) {
          var c = r.get(f), d = c?.v;
          if (c !== void 0 && d !== P)
            return {
              enumerable: !0,
              configurable: !0,
              value: d,
              writable: !0
            };
        }
        return a;
      },
      has(l, f) {
        if (f === vt)
          return !0;
        var a = r.get(f), u = a !== void 0 && a.v !== P || Reflect.has(l, f);
        if (a !== void 0 || y !== null && (!u || qe(l, f)?.writable)) {
          a === void 0 && (a = o(() => {
            var d = u ? je(l[f]) : P, v = /* @__PURE__ */ me(d);
            return v;
          }), r.set(f, a));
          var c = b(a);
          if (c === P)
            return !1;
        }
        return u;
      },
      set(l, f, a, u) {
        var c = r.get(f), d = f in l;
        if (n && f === "length")
          for (var v = a; v < /** @type {Source<number>} */
          c.v; v += 1) {
            var h = r.get(v + "");
            h !== void 0 ? te(h, P) : v in l && (h = o(() => /* @__PURE__ */ me(P)), r.set(v + "", h));
          }
        if (c === void 0)
          (!d || qe(l, f)?.writable) && (c = o(() => /* @__PURE__ */ me(void 0)), te(c, je(a)), r.set(f, c));
        else {
          d = c.v !== P;
          var p = o(() => je(a));
          te(c, p);
        }
        var _ = Reflect.getOwnPropertyDescriptor(l, f);
        if (_?.set && _.set.call(u, a), !d) {
          if (n && typeof f == "string") {
            var $ = (
              /** @type {Source<number>} */
              r.get("length")
            ), g = Number(f);
            Number.isInteger(g) && g >= $.v && te($, g + 1);
          }
          _t(s);
        }
        return !0;
      },
      ownKeys(l) {
        b(s);
        var f = Reflect.ownKeys(l).filter((c) => {
          var d = r.get(c);
          return d === void 0 || d.v !== P;
        });
        for (var [a, u] of r)
          u.v !== P && !(a in l) && f.push(a);
        return f;
      },
      setPrototypeOf() {
        Ls();
      }
    }
  );
}
var Tr, vn, pn, _n;
function Gt() {
  if (Tr === void 0) {
    Tr = window, vn = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, t = Node.prototype, r = Text.prototype;
    pn = qe(t, "firstChild").get, _n = qe(t, "nextSibling").get, kr(e) && (e.__click = void 0, e.__className = void 0, e.__attributes = null, e.__style = void 0, e.__e = void 0), kr(r) && (r.__t = void 0);
  }
}
function ie(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function ne(e) {
  return (
    /** @type {TemplateNode | null} */
    pn.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function ve(e) {
  return (
    /** @type {TemplateNode | null} */
    _n.call(e)
  );
}
function B(e, t) {
  if (!N)
    return /* @__PURE__ */ ne(e);
  var r = /* @__PURE__ */ ne(x);
  if (r === null)
    r = x.appendChild(ie());
  else if (t && r.nodeType !== Lt) {
    var n = ie();
    return r?.before(n), j(n), n;
  }
  return t && fr(
    /** @type {Text} */
    r
  ), j(r), r;
}
function Kt(e, t = !1) {
  if (!N) {
    var r = /* @__PURE__ */ ne(e);
    return r instanceof Comment && r.data === "" ? /* @__PURE__ */ ve(r) : r;
  }
  if (t) {
    if (x?.nodeType !== Lt) {
      var n = ie();
      return x?.before(n), j(n), n;
    }
    fr(
      /** @type {Text} */
      x
    );
  }
  return x;
}
function $e(e, t = 1, r = !1) {
  let n = N ? x : e;
  for (var s; t--; )
    s = n, n = /** @type {TemplateNode} */
    /* @__PURE__ */ ve(n);
  if (!N)
    return n;
  if (r) {
    if (n?.nodeType !== Lt) {
      var i = ie();
      return n === null ? s?.after(i) : n.before(i), j(i), i;
    }
    fr(
      /** @type {Text} */
      n
    );
  }
  return j(n), n;
}
function gn(e) {
  e.textContent = "";
}
function bn() {
  return !1;
}
function Ft(e, t, r) {
  return (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    document.createElementNS(t ?? zr, e, void 0)
  );
}
function fr(e) {
  if (
    /** @type {string} */
    e.nodeValue.length < 65536
  )
    return;
  let t = e.nextSibling;
  for (; t !== null && t.nodeType === Lt; )
    t.remove(), e.nodeValue += /** @type {string} */
    t.nodeValue, t = e.nextSibling;
}
function yt(e) {
  var t = A, r = y;
  oe(null), ge(null);
  try {
    return e();
  } finally {
    oe(t), ge(r);
  }
}
function ri(e) {
  y === null && (A === null && Ns(), As()), Me && Ss();
}
function ni(e, t) {
  var r = t.last;
  r === null ? t.last = t.first = e : (r.next = e, e.prev = r, t.last = e);
}
function be(e, t) {
  var r = y;
  r !== null && r.f & V && (e |= V);
  var n = {
    ctx: G,
    deps: null,
    nodes: null,
    f: e | z | se,
    first: null,
    fn: t,
    last: null,
    next: null,
    parent: r,
    b: r && r.b,
    prev: null,
    teardown: null,
    wv: 0,
    ac: null
  };
  S?.register_created_effect(n);
  var s = n;
  if (e & nt)
    et !== null ? et.push(n) : Oe.ensure().schedule(n);
  else if (t !== null) {
    try {
      ot(n);
    } catch (o) {
      throw Y(n), o;
    }
    s.deps === null && s.teardown === null && s.nodes === null && s.first === s.last && // either `null`, or a singular child
    !(s.f & Xe) && (s = s.first, e & he && e & Ke && s !== null && (s.f |= Ke));
  }
  if (s !== null && (s.parent = r, r !== null && ni(s, r), A !== null && A.f & H && !(e & Ne))) {
    var i = (
      /** @type {Derived} */
      A
    );
    (i.effects ??= []).push(s);
  }
  return n;
}
function ur() {
  return A !== null && !ce;
}
function cr(e) {
  const t = be(Rt, null);
  return R(t, D), t.teardown = e, t;
}
function mn(e) {
  ri();
  var t = (
    /** @type {Effect} */
    y.f
  ), r = !A && (t & de) !== 0 && (t & Ce) === 0;
  if (r) {
    var n = (
      /** @type {ComponentContext} */
      G
    );
    (n.e ??= []).push(e);
  } else
    return wn(e);
}
function wn(e) {
  return be(nt | $s, e);
}
function si(e) {
  Oe.ensure();
  const t = be(Ne | Xe, e);
  return () => {
    Y(t);
  };
}
function ii(e) {
  Oe.ensure();
  const t = be(Ne | Xe, e);
  return (r = {}) => new Promise((n) => {
    r.outro ? Ue(t, () => {
      Y(t), n(void 0);
    }) : (Y(t), n(void 0));
  });
}
function hr(e) {
  return be(nt, e);
}
function li(e) {
  return be(bt | Xe, e);
}
function dr(e, t = 0) {
  return be(Rt | t, e);
}
function Te(e, t = [], r = [], n = []) {
  Js(n, t, r, (s) => {
    be(Rt, () => e(...s.map(b)));
  });
}
function vr(e, t = 0) {
  var r = be(he | t, e);
  return r;
}
function ee(e) {
  return be(de | Xe, e);
}
function yn(e) {
  var t = e.teardown;
  if (t !== null) {
    const r = Me, n = A;
    Sr(!0), oe(null);
    try {
      t.call(null);
    } finally {
      Sr(r), oe(n);
    }
  }
}
function pr(e, t = !1) {
  var r = e.first;
  for (e.first = e.last = null; r !== null; ) {
    const s = r.ac;
    s !== null && yt(() => {
      s.abort(ye);
    });
    var n = r.next;
    r.f & Ne ? r.parent = null : Y(r, t), r = n;
  }
}
function oi(e) {
  for (var t = e.first; t !== null; ) {
    var r = t.next;
    t.f & de || Y(t), t = r;
  }
}
function Y(e, t = !0) {
  var r = !1;
  (t || e.f & ys) && e.nodes !== null && e.nodes.end !== null && ($n(
    e.nodes.start,
    /** @type {TemplateNode} */
    e.nodes.end
  ), r = !0), R(e, qt), pr(e, t && !r), mt(e, 0);
  var n = e.nodes && e.nodes.t;
  if (n !== null)
    for (const i of n)
      i.stop();
  yn(e), e.f ^= qt, e.f |= Z;
  var s = e.parent;
  s !== null && s.first !== null && kn(e), e.next = e.prev = e.teardown = e.ctx = e.deps = e.fn = e.nodes = e.ac = e.b = null;
}
function $n(e, t) {
  for (; e !== null; ) {
    var r = e === t ? null : /* @__PURE__ */ ve(e);
    e.remove(), e = r;
  }
}
function kn(e) {
  var t = e.parent, r = e.prev, n = e.next;
  r !== null && (r.next = n), n !== null && (n.prev = r), t !== null && (t.first === e && (t.first = n), t.last === e && (t.last = r));
}
function Ue(e, t, r = !0) {
  var n = [];
  En(e, n, !0);
  var s = () => {
    r && Y(e), t && t();
  }, i = n.length;
  if (i > 0) {
    var o = () => --i || s();
    for (var l of n)
      l.out(o);
  } else
    s();
}
function En(e, t, r) {
  if (!(e.f & V)) {
    e.f ^= V;
    var n = e.nodes && e.nodes.t;
    if (n !== null)
      for (const l of n)
        (l.is_global || r) && t.push(l);
    for (var s = e.first; s !== null; ) {
      var i = s.next;
      if (!(s.f & Ne)) {
        var o = (s.f & Ke) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (s.f & de) !== 0 && (e.f & he) !== 0;
        En(s, t, o ? r : !1);
      }
      s = i;
    }
  }
}
function _r(e) {
  xn(e, !0);
}
function xn(e, t) {
  if (e.f & V) {
    e.f ^= V, e.f & D || (R(e, z), Oe.ensure().schedule(e));
    for (var r = e.first; r !== null; ) {
      var n = r.next, s = (r.f & Ke) !== 0 || (r.f & de) !== 0;
      xn(r, s ? t : !1), r = n;
    }
    var i = e.nodes && e.nodes.t;
    if (i !== null)
      for (const o of i)
        (o.is_global || t) && o.in();
  }
}
function gr(e, t) {
  if (e.nodes)
    for (var r = e.nodes.start, n = e.nodes.end; r !== null; ) {
      var s = r === n ? null : /* @__PURE__ */ ve(r);
      t.append(r), r = s;
    }
}
let Tt = !1, Me = !1;
function Sr(e) {
  Me = e;
}
let A = null, ce = !1;
function oe(e) {
  A = e;
}
let y = null;
function ge(e) {
  y = e;
}
let le = null;
function Tn(e) {
  A !== null && (le === null ? le = [e] : le.push(e));
}
let W = null, J = 0, Q = null;
function ai(e) {
  Q = e;
}
let Sn = 1, He = 0, Ve = He;
function Ar(e) {
  Ve = e;
}
function An() {
  return ++Sn;
}
function $t(e) {
  var t = e.f;
  if (t & z)
    return !0;
  if (t & H && (e.f &= ~Je), t & _e) {
    for (var r = (
      /** @type {Value[]} */
      e.deps
    ), n = r.length, s = 0; s < n; s++) {
      var i = r[s];
      if ($t(
        /** @type {Derived} */
        i
      ) && un(
        /** @type {Derived} */
        i
      ), i.wv > e.wv)
        return !0;
    }
    t & se && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    ue === null && R(e, D);
  }
  return !1;
}
function Nn(e, t, r = !0) {
  var n = e.reactions;
  if (n !== null && !(le !== null && rt.call(le, e)))
    for (var s = 0; s < n.length; s++) {
      var i = n[s];
      i.f & H ? Nn(
        /** @type {Derived} */
        i,
        t,
        !1
      ) : t === i && (r ? R(i, z) : i.f & D && R(i, _e), lr(
        /** @type {Effect} */
        i
      ));
    }
}
function On(e) {
  var t = W, r = J, n = Q, s = A, i = le, o = G, l = ce, f = Ve, a = e.f;
  W = /** @type {null | Value[]} */
  null, J = 0, Q = null, A = a & (de | Ne) ? null : e, le = null, it(e.ctx), ce = !1, Ve = ++He, e.ac !== null && (yt(() => {
    e.ac.abort(ye);
  }), e.ac = null);
  try {
    e.f |= Nt;
    var u = (
      /** @type {Function} */
      e.fn
    ), c = u();
    e.f |= Ce;
    var d = e.deps, v = S?.is_fork;
    if (W !== null) {
      var h;
      if (v || mt(e, J), d !== null && J > 0)
        for (d.length = J + W.length, h = 0; h < W.length; h++)
          d[J + h] = W[h];
      else
        e.deps = d = W;
      if (ur() && e.f & se)
        for (h = J; h < d.length; h++)
          (d[h].reactions ??= []).push(e);
    } else !v && d !== null && J < d.length && (mt(e, J), d.length = J);
    if (Jr() && Q !== null && !ce && d !== null && !(e.f & (H | _e | z)))
      for (h = 0; h < /** @type {Source[]} */
      Q.length; h++)
        Nn(
          Q[h],
          /** @type {Effect} */
          e
        );
    if (s !== null && s !== e) {
      if (He++, s.deps !== null)
        for (let p = 0; p < r; p += 1)
          s.deps[p].rv = He;
      if (t !== null)
        for (const p of t)
          p.rv = He;
      Q !== null && (n === null ? n = Q : n.push(.../** @type {Source[]} */
      Q));
    }
    return e.f & De && (e.f ^= De), c;
  } catch (p) {
    return Xr(p);
  } finally {
    e.f ^= Nt, W = t, J = r, Q = n, A = s, le = i, it(o), ce = l, Ve = f;
  }
}
function fi(e, t) {
  let r = t.reactions;
  if (r !== null) {
    var n = vs.call(r, e);
    if (n !== -1) {
      var s = r.length - 1;
      s === 0 ? r = t.reactions = null : (r[n] = r[s], r.pop());
    }
  }
  if (r === null && t.f & H && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (W === null || !rt.call(W, t))) {
    var i = (
      /** @type {Derived} */
      t
    );
    i.f & se && (i.f ^= se, i.f &= ~Je), i.v !== P && sr(i), ei(i), mt(i, 0);
  }
}
function mt(e, t) {
  var r = e.deps;
  if (r !== null)
    for (var n = t; n < r.length; n++)
      fi(e, r[n]);
}
function ot(e) {
  var t = e.f;
  if (!(t & Z)) {
    R(e, D);
    var r = y, n = Tt;
    y = e, Tt = !0;
    try {
      t & (he | Br) ? oi(e) : pr(e), yn(e);
      var s = On(e);
      e.teardown = typeof s == "function" ? s : null, e.wv = Sn;
      var i;
      ds && zs && e.f & z && e.deps;
    } finally {
      Tt = n, y = r;
    }
  }
}
async function ui() {
  await Promise.resolve(), Se();
}
function b(e) {
  var t = e.f, r = (t & H) !== 0;
  if (A !== null && !ce) {
    var n = y !== null && (y.f & Z) !== 0;
    if (!n && (le === null || !rt.call(le, e))) {
      var s = A.deps;
      if (A.f & Nt)
        e.rv < He && (e.rv = He, W === null && s !== null && s[J] === e ? J++ : W === null ? W = [e] : W.push(e));
      else {
        (A.deps ??= []).push(e);
        var i = e.reactions;
        i === null ? e.reactions = [A] : rt.call(i, A) || i.push(A);
      }
    }
  }
  if (Me && Be.has(e))
    return Be.get(e);
  if (r) {
    var o = (
      /** @type {Derived} */
      e
    );
    if (Me) {
      var l = o.v;
      return (!(o.f & D) && o.reactions !== null || Cn(o)) && (l = or(o)), Be.set(o, l), l;
    }
    var f = (o.f & se) === 0 && !ce && A !== null && (Tt || (A.f & se) !== 0), a = (o.f & Ce) === 0;
    $t(o) && (f && (o.f |= se), un(o)), f && !a && (cn(o), Mn(o));
  }
  if (ue?.has(e))
    return ue.get(e);
  if (e.f & De)
    throw e.v;
  return e.v;
}
function Mn(e) {
  if (e.f |= se, e.deps !== null)
    for (const t of e.deps)
      (t.reactions ??= []).push(e), t.f & H && !(t.f & se) && (cn(
        /** @type {Derived} */
        t
      ), Mn(
        /** @type {Derived} */
        t
      ));
}
function Cn(e) {
  if (e.v === P) return !0;
  if (e.deps === null) return !1;
  for (const t of e.deps)
    if (Be.has(t) || t.f & H && Cn(
      /** @type {Derived} */
      t
    ))
      return !0;
  return !1;
}
function ft(e) {
  var t = ce;
  try {
    return ce = !0, e();
  } finally {
    ce = t;
  }
}
const ht = Symbol("events"), Rn = /* @__PURE__ */ new Set(), Jt = /* @__PURE__ */ new Set();
function ci(e, t, r, n = {}) {
  function s(i) {
    if (n.capture || Zt.call(t, i), !i.cancelBubble)
      return yt(() => r?.call(this, i));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? Pe(() => {
    t.addEventListener(e, s, n);
  }) : t.addEventListener(e, s, n), s;
}
function hi(e, t, r, n, s) {
  var i = { capture: n, passive: s }, o = ci(e, t, r, i);
  (t === document.body || // @ts-ignore
  t === window || // @ts-ignore
  t === document || // Firefox has quirky behavior, it can happen that we still get "canplay" events when the element is already removed
  t instanceof HTMLMediaElement) && cr(() => {
    t.removeEventListener(e, o, i);
  });
}
function Nr(e, t, r) {
  (t[ht] ??= {})[e] = r;
}
function di(e) {
  for (var t = 0; t < e.length; t++)
    Rn.add(e[t]);
  for (var r of Jt)
    r(e);
}
let Or = null;
function Zt(e) {
  var t = this, r = (
    /** @type {Node} */
    t.ownerDocument
  ), n = e.type, s = e.composedPath?.() || [], i = (
    /** @type {null | Element} */
    s[0] || e.target
  );
  Or = e;
  var o = 0, l = Or === e && e[ht];
  if (l) {
    var f = s.indexOf(l);
    if (f !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e[ht] = t;
      return;
    }
    var a = s.indexOf(t);
    if (a === -1)
      return;
    f <= a && (o = f);
  }
  if (i = /** @type {Element} */
  s[o] || e.target, i !== t) {
    gt(e, "currentTarget", {
      configurable: !0,
      get() {
        return i || r;
      }
    });
    var u = A, c = y;
    oe(null), ge(null);
    try {
      for (var d, v = []; i !== null; ) {
        var h = i.assignedSlot || i.parentNode || /** @type {any} */
        i.host || null;
        try {
          var p = i[ht]?.[n];
          p != null && (!/** @type {any} */
          i.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === i) && p.call(i, e);
        } catch (_) {
          d ? v.push(_) : d = _;
        }
        if (e.cancelBubble || h === t || h === null)
          break;
        i = h;
      }
      if (d) {
        for (let _ of v)
          queueMicrotask(() => {
            throw _;
          });
        throw d;
      }
    } finally {
      e[ht] = t, delete e.currentTarget, oe(u), ge(c);
    }
  }
}
const vi = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  globalThis?.window?.trustedTypes && /* @__PURE__ */ globalThis.window.trustedTypes.createPolicy("svelte-trusted-html", {
    /** @param {string} html */
    createHTML: (e) => e
  })
);
function pi(e) {
  return (
    /** @type {string} */
    vi?.createHTML(e) ?? e
  );
}
function _i(e) {
  var t = Ft("template");
  return t.innerHTML = pi(e.replaceAll("<!>", "<!---->")), t.content;
}
function Ae(e, t) {
  var r = (
    /** @type {Effect} */
    y
  );
  r.nodes === null && (r.nodes = { start: e, end: t, a: null, t: null });
}
// @__NO_SIDE_EFFECTS__
function ae(e, t) {
  var r = (t & fs) !== 0, n = (t & us) !== 0, s, i = !e.startsWith("<!>");
  return () => {
    if (N)
      return Ae(x, null), x;
    s === void 0 && (s = _i(i ? e : "<!>" + e), r || (s = /** @type {TemplateNode} */
    /* @__PURE__ */ ne(s)));
    var o = (
      /** @type {TemplateNode} */
      n || vn ? document.importNode(s, !0) : s.cloneNode(!0)
    );
    if (r) {
      var l = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ ne(o)
      ), f = (
        /** @type {TemplateNode} */
        o.lastChild
      );
      Ae(l, f);
    } else
      Ae(o, o);
    return o;
  };
}
function Ln() {
  if (N)
    return Ae(x, null), x;
  var e = document.createDocumentFragment(), t = document.createComment(""), r = ie();
  return e.append(t, r), Ae(t, r), e;
}
function U(e, t) {
  if (N) {
    var r = (
      /** @type {Effect & { nodes: EffectNodes }} */
      y
    );
    (!(r.f & Ce) || r.nodes.end === null) && (r.nodes.end = x), st();
    return;
  }
  e !== null && e.before(
    /** @type {Node} */
    t
  );
}
const gi = ["touchstart", "touchmove"];
function bi(e) {
  return gi.includes(e);
}
let Xt = !0;
function fe(e, t) {
  var r = t == null ? "" : typeof t == "object" ? `${t}` : t;
  r !== (e.__t ??= e.nodeValue) && (e.__t = r, e.nodeValue = `${r}`);
}
function In(e, t) {
  return Dn(e, t);
}
function mi(e, t) {
  Gt(), t.intro = t.intro ?? !1;
  const r = t.target, n = N, s = x;
  try {
    for (var i = /* @__PURE__ */ ne(r); i && (i.nodeType !== at || /** @type {Comment} */
    i.data !== Fr); )
      i = /* @__PURE__ */ ve(i);
    if (!i)
      throw Ge;
    xe(!0), j(
      /** @type {Comment} */
      i
    );
    const o = Dn(e, { ...t, anchor: i });
    return xe(!1), /**  @type {Exports} */
    o;
  } catch (o) {
    if (o instanceof Error && o.message.split(`
`).some((l) => l.startsWith("https://svelte.dev/e/")))
      throw o;
    return o !== Ge && console.warn("Failed to hydrate: ", o), t.recover === !1 && Ms(), Gt(), gn(r), xe(!1), In(e, t);
  } finally {
    xe(n), j(s);
  }
}
const Et = /* @__PURE__ */ new Map();
function Dn(e, { target: t, anchor: r, props: n = {}, events: s, context: i, intro: o = !0, transformError: l }) {
  Gt();
  var f = void 0, a = ii(() => {
    var u = r ?? t.appendChild(ie());
    Gs(
      /** @type {TemplateNode} */
      u,
      {
        pending: () => {
        }
      },
      (v) => {
        It({});
        var h = (
          /** @type {ComponentContext} */
          G
        );
        if (i && (h.c = i), s && (n.$$events = s), N && Ae(
          /** @type {TemplateNode} */
          v,
          null
        ), Xt = o, f = e(v, n) || {}, Xt = !0, N && (y.nodes.end = x, x === null || x.nodeType !== at || /** @type {Comment} */
        x.data !== nr))
          throw wt(), Ge;
        Dt();
      },
      l
    );
    var c = /* @__PURE__ */ new Set(), d = (v) => {
      for (var h = 0; h < v.length; h++) {
        var p = v[h];
        if (!c.has(p)) {
          c.add(p);
          var _ = bi(p);
          for (const C of [t, document]) {
            var $ = Et.get(C);
            $ === void 0 && ($ = /* @__PURE__ */ new Map(), Et.set(C, $));
            var g = $.get(p);
            g === void 0 ? (C.addEventListener(p, Zt, { passive: _ }), $.set(p, 1)) : $.set(p, g + 1);
          }
        }
      }
    };
    return d(Ct(Rn)), Jt.add(d), () => {
      for (var v of c)
        for (const _ of [t, document]) {
          var h = (
            /** @type {Map<string, number>} */
            Et.get(_)
          ), p = (
            /** @type {number} */
            h.get(v)
          );
          --p == 0 ? (_.removeEventListener(v, Zt), h.delete(v), h.size === 0 && Et.delete(_)) : h.set(v, p);
        }
      Jt.delete(d), u !== r && u.parentNode?.removeChild(u);
    };
  });
  return Qt.set(f, a), f;
}
let Qt = /* @__PURE__ */ new WeakMap();
function wi(e, t) {
  const r = Qt.get(e);
  return r ? (Qt.delete(e), r(t)) : Promise.resolve();
}
class yi {
  /** @type {TemplateNode} */
  anchor;
  /** @type {Map<Batch, Key>} */
  #e = /* @__PURE__ */ new Map();
  /**
   * Map of keys to effects that are currently rendered in the DOM.
   * These effects are visible and actively part of the document tree.
   * Example:
   * ```
   * {#if condition}
   * 	foo
   * {:else}
   * 	bar
   * {/if}
   * ```
   * Can result in the entries `true->Effect` and `false->Effect`
   * @type {Map<Key, Effect>}
   */
  #n = /* @__PURE__ */ new Map();
  /**
   * Similar to #onscreen with respect to the keys, but contains branches that are not yet
   * in the DOM, because their insertion is deferred.
   * @type {Map<Key, Branch>}
   */
  #t = /* @__PURE__ */ new Map();
  /**
   * Keys of effects that are currently outroing
   * @type {Set<Key>}
   */
  #i = /* @__PURE__ */ new Set();
  /**
   * Whether to pause (i.e. outro) on change, or destroy immediately.
   * This is necessary for `<svelte:element>`
   */
  #s = !0;
  /**
   * @param {TemplateNode} anchor
   * @param {boolean} transition
   */
  constructor(t, r = !0) {
    this.anchor = t, this.#s = r;
  }
  /**
   * @param {Batch} batch
   */
  #l = (t) => {
    if (this.#e.has(t)) {
      var r = (
        /** @type {Key} */
        this.#e.get(t)
      ), n = this.#n.get(r);
      if (n)
        _r(n), this.#i.delete(r);
      else {
        var s = this.#t.get(r);
        s && (this.#n.set(r, s.effect), this.#t.delete(r), s.fragment.lastChild.remove(), this.anchor.before(s.fragment), n = s.effect);
      }
      for (const [i, o] of this.#e) {
        if (this.#e.delete(i), i === t)
          break;
        const l = this.#t.get(o);
        l && (Y(l.effect), this.#t.delete(o));
      }
      for (const [i, o] of this.#n) {
        if (i === r || this.#i.has(i)) continue;
        const l = () => {
          if (Array.from(this.#e.values()).includes(i)) {
            var a = document.createDocumentFragment();
            gr(o, a), a.append(ie()), this.#t.set(i, { effect: o, fragment: a });
          } else
            Y(o);
          this.#i.delete(i), this.#n.delete(i);
        };
        this.#s || !n ? (this.#i.add(i), Ue(o, l, !1)) : l();
      }
    }
  };
  /**
   * @param {Batch} batch
   */
  #r = (t) => {
    this.#e.delete(t);
    const r = Array.from(this.#e.values());
    for (const [n, s] of this.#t)
      r.includes(n) || (Y(s.effect), this.#t.delete(n));
  };
  /**
   *
   * @param {any} key
   * @param {null | ((target: TemplateNode) => void)} fn
   */
  ensure(t, r) {
    var n = (
      /** @type {Batch} */
      S
    ), s = bn();
    if (r && !this.#n.has(t) && !this.#t.has(t))
      if (s) {
        var i = document.createDocumentFragment(), o = ie();
        i.append(o), this.#t.set(t, {
          effect: ee(() => r(o)),
          fragment: i
        });
      } else
        this.#n.set(
          t,
          ee(() => r(this.anchor))
        );
    if (this.#e.set(n, t), s) {
      for (const [l, f] of this.#n)
        l === t ? n.unskip_effect(f) : n.skip_effect(f);
      for (const [l, f] of this.#t)
        l === t ? n.unskip_effect(f.effect) : n.skip_effect(f.effect);
      n.oncommit(this.#l), n.ondiscard(this.#r);
    } else
      N && (this.anchor = x), this.#l(n);
  }
}
function $i(e) {
  G === null && Es(), mn(() => {
    const t = ft(e);
    if (typeof t == "function") return (
      /** @type {() => void} */
      t
    );
  });
}
function Ye(e, t, r = !1) {
  var n;
  N && (n = x, st());
  var s = new yi(e), i = r ? Ke : 0;
  function o(l, f) {
    if (N) {
      var a = Yr(
        /** @type {TemplateNode} */
        n
      );
      if (l !== parseInt(a.substring(1))) {
        var u = Ot();
        j(u), s.anchor = u, xe(!1), s.ensure(l, f), xe(!0);
        return;
      }
    }
    s.ensure(l, f);
  }
  vr(() => {
    var l = !1;
    t((f, a = 0) => {
      l = !0, o(a, f);
    }), l || o(-1, null);
  }, i);
}
function ki(e, t) {
  return t;
}
function Ei(e, t, r) {
  for (var n = [], s = t.length, i, o = t.length, l = 0; l < s; l++) {
    let c = t[l];
    Ue(
      c,
      () => {
        if (i) {
          if (i.pending.delete(c), i.done.add(c), i.pending.size === 0) {
            var d = (
              /** @type {Set<EachOutroGroup>} */
              e.outrogroups
            );
            er(e, Ct(i.done)), d.delete(i), d.size === 0 && (e.outrogroups = null);
          }
        } else
          o -= 1;
      },
      !1
    );
  }
  if (o === 0) {
    var f = n.length === 0 && r !== null;
    if (f) {
      var a = (
        /** @type {Element} */
        r
      ), u = (
        /** @type {Element} */
        a.parentNode
      );
      gn(u), u.append(a), e.items.clear();
    }
    er(e, t, !f);
  } else
    i = {
      pending: new Set(t),
      done: /* @__PURE__ */ new Set()
    }, (e.outrogroups ??= /* @__PURE__ */ new Set()).add(i);
}
function er(e, t, r = !0) {
  var n;
  if (e.pending.size > 0) {
    n = /* @__PURE__ */ new Set();
    for (const o of e.pending.values())
      for (const l of o)
        n.add(
          /** @type {EachItem} */
          e.items.get(l).e
        );
  }
  for (var s = 0; s < t.length; s++) {
    var i = t[s];
    if (n?.has(i)) {
      i.f |= Ee;
      const o = document.createDocumentFragment();
      gr(i, o);
    } else
      Y(t[s], r);
  }
}
var Mr;
function Pn(e, t, r, n, s, i = null) {
  var o = e, l = /* @__PURE__ */ new Map();
  {
    var f = (
      /** @type {Element} */
      e
    );
    o = N ? j(/* @__PURE__ */ ne(f)) : f.appendChild(ie());
  }
  N && st();
  var a = null, u = /* @__PURE__ */ fn(() => {
    var g = r();
    return jr(g) ? g : g == null ? [] : Ct(g);
  }), c, d = /* @__PURE__ */ new Map(), v = !0;
  function h(g) {
    $.effect.f & Z || ($.pending.delete(g), $.fallback = a, xi($, c, o, t, n), a !== null && (c.length === 0 ? a.f & Ee ? (a.f ^= Ee, dt(a, null, o)) : _r(a) : Ue(a, () => {
      a = null;
    })));
  }
  function p(g) {
    $.pending.delete(g);
  }
  var _ = vr(() => {
    c = /** @type {V[]} */
    b(u);
    var g = c.length;
    let C = !1;
    if (N) {
      var w = Yr(o) === rr;
      w !== (g === 0) && (o = Ot(), j(o), xe(!1), C = !0);
    }
    for (var m = /* @__PURE__ */ new Set(), T = (
      /** @type {Batch} */
      S
    ), M = bn(), E = 0; E < g; E += 1) {
      N && x.nodeType === at && /** @type {Comment} */
      x.data === nr && (o = /** @type {Comment} */
      x, C = !0, xe(!1));
      var L = c[E], q = n(L, E), O = v ? null : l.get(q);
      O ? (O.v && lt(O.v, L), O.i && lt(O.i, E), M && T.unskip_effect(O.e)) : (O = Ti(
        l,
        v ? o : Mr ??= ie(),
        L,
        q,
        E,
        s,
        t,
        r
      ), v || (O.e.f |= Ee), l.set(q, O)), m.add(q);
    }
    if (g === 0 && i && !a && (v ? a = ee(() => i(o)) : (a = ee(() => i(Mr ??= ie())), a.f |= Ee)), g > m.size && Ts(), N && g > 0 && j(Ot()), !v)
      if (d.set(T, m), M) {
        for (const [k, I] of l)
          m.has(k) || T.skip_effect(I.e);
        T.oncommit(h), T.ondiscard(p);
      } else
        h(T);
    C && xe(!0), b(u);
  }), $ = { effect: _, items: l, pending: d, outrogroups: null, fallback: a };
  v = !1, N && (o = x);
}
function ct(e) {
  for (; e !== null && !(e.f & de); )
    e = e.next;
  return e;
}
function xi(e, t, r, n, s) {
  var i = t.length, o = e.items, l = ct(e.effect.first), f, a = null, u = [], c = [], d, v, h, p;
  for (p = 0; p < i; p += 1) {
    if (d = t[p], v = s(d, p), h = /** @type {EachItem} */
    o.get(v).e, e.outrogroups !== null)
      for (const E of e.outrogroups)
        E.pending.delete(h), E.done.delete(h);
    if (h.f & V && _r(h), h.f & Ee)
      if (h.f ^= Ee, h === l)
        dt(h, null, r);
      else {
        var _ = a ? a.next : l;
        h === e.effect.last && (e.effect.last = h.prev), h.prev && (h.prev.next = h.next), h.next && (h.next.prev = h.prev), Re(e, a, h), Re(e, h, _), dt(h, _, r), a = h, u = [], c = [], l = ct(a.next);
        continue;
      }
    if (h !== l) {
      if (f !== void 0 && f.has(h)) {
        if (u.length < c.length) {
          var $ = c[0], g;
          a = $.prev;
          var C = u[0], w = u[u.length - 1];
          for (g = 0; g < u.length; g += 1)
            dt(u[g], $, r);
          for (g = 0; g < c.length; g += 1)
            f.delete(c[g]);
          Re(e, C.prev, w.next), Re(e, a, C), Re(e, w, $), l = $, a = w, p -= 1, u = [], c = [];
        } else
          f.delete(h), dt(h, l, r), Re(e, h.prev, h.next), Re(e, h, a === null ? e.effect.first : a.next), Re(e, a, h), a = h;
        continue;
      }
      for (u = [], c = []; l !== null && l !== h; )
        (f ??= /* @__PURE__ */ new Set()).add(l), c.push(l), l = ct(l.next);
      if (l === null)
        continue;
    }
    h.f & Ee || u.push(h), a = h, l = ct(h.next);
  }
  if (e.outrogroups !== null) {
    for (const E of e.outrogroups)
      E.pending.size === 0 && (er(e, Ct(E.done)), e.outrogroups?.delete(E));
    e.outrogroups.size === 0 && (e.outrogroups = null);
  }
  if (l !== null || f !== void 0) {
    var m = [];
    if (f !== void 0)
      for (h of f)
        h.f & V || m.push(h);
    for (; l !== null; )
      !(l.f & V) && l !== e.fallback && m.push(l), l = ct(l.next);
    var T = m.length;
    if (T > 0) {
      var M = i === 0 ? r : null;
      Ei(e, m, M);
    }
  }
}
function Ti(e, t, r, n, s, i, o, l) {
  var f = o & ts ? o & ns ? Ze(r) : /* @__PURE__ */ ar(r, !1, !1) : null, a = o & rs ? Ze(s) : null;
  return {
    v: f,
    i: a,
    e: ee(() => (i(t, f ?? r, a ?? s, l), () => {
      e.delete(n);
    }))
  };
}
function dt(e, t, r) {
  if (e.nodes)
    for (var n = e.nodes.start, s = e.nodes.end, i = t && !(t.f & Ee) ? (
      /** @type {EffectNodes} */
      t.nodes.start
    ) : r; n !== null; ) {
      var o = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ ve(n)
      );
      if (i.before(n), n === s)
        return;
      n = o;
    }
}
function Re(e, t, r) {
  t === null ? e.effect.first = r : t.next = r, r === null ? e.effect.last = t : r.prev = t;
}
function Si(e, t, r = !1, n = !1, s = !1, i = !1) {
  var o = e, l = "";
  if (r) {
    var f = (
      /** @type {Element} */
      e
    );
    N && (o = j(/* @__PURE__ */ ne(f)));
  }
  Te(() => {
    var a = (
      /** @type {Effect} */
      y
    );
    if (l === (l = t() ?? "")) {
      N && st();
      return;
    }
    if (r && !N) {
      a.nodes = null, f.innerHTML = /** @type {string} */
      l, l !== "" && Ae(
        /** @type {TemplateNode} */
        /* @__PURE__ */ ne(f),
        /** @type {TemplateNode} */
        f.lastChild
      );
      return;
    }
    if (a.nodes !== null && ($n(
      a.nodes.start,
      /** @type {TemplateNode} */
      a.nodes.end
    ), a.nodes = null), l !== "") {
      if (N) {
        x.data;
        for (var u = st(), c = u; u !== null && (u.nodeType !== at || /** @type {Comment} */
        u.data !== ""); )
          c = u, u = /* @__PURE__ */ ve(u);
        if (u === null)
          throw wt(), Ge;
        Ae(x, c), o = j(u);
        return;
      }
      var d = n ? cs : s ? hs : void 0, v = (
        /** @type {HTMLTemplateElement | SVGElement | MathMLElement} */
        Ft(n ? "svg" : s ? "math" : "template", d)
      );
      v.innerHTML = /** @type {any} */
      l;
      var h = n || s ? v : (
        /** @type {HTMLTemplateElement} */
        v.content
      );
      if (Ae(
        /** @type {TemplateNode} */
        /* @__PURE__ */ ne(h),
        /** @type {TemplateNode} */
        h.lastChild
      ), n || s)
        for (; /* @__PURE__ */ ne(h); )
          o.before(
            /** @type {TemplateNode} */
            /* @__PURE__ */ ne(h)
          );
      else
        o.before(h);
    }
  });
}
const Ai = () => performance.now(), ke = {
  // don't access requestAnimationFrame eagerly outside method
  // this allows basic testing of user code without JSDOM
  // bunder will eval and remove ternary when the user's app is built
  tick: (
    /** @param {any} _ */
    (e) => requestAnimationFrame(e)
  ),
  now: () => Ai(),
  tasks: /* @__PURE__ */ new Set()
};
function Fn() {
  const e = ke.now();
  ke.tasks.forEach((t) => {
    t.c(e) || (ke.tasks.delete(t), t.f());
  }), ke.tasks.size !== 0 && ke.tick(Fn);
}
function Ni(e) {
  let t;
  return ke.tasks.size === 0 && ke.tick(Fn), {
    promise: new Promise((r) => {
      ke.tasks.add(t = { c: e, f: r });
    }),
    abort() {
      ke.tasks.delete(t);
    }
  };
}
function Cr(e, t) {
  yt(() => {
    e.dispatchEvent(new CustomEvent(t));
  });
}
function Oi(e) {
  if (e === "float") return "cssFloat";
  if (e === "offset") return "cssOffset";
  if (e.startsWith("--")) return e;
  const t = e.split("-");
  return t.length === 1 ? t[0] : t[0] + t.slice(1).map(
    /** @param {any} word */
    (r) => r[0].toUpperCase() + r.slice(1)
  ).join("");
}
function Rr(e) {
  const t = {}, r = e.split(";");
  for (const n of r) {
    const [s, i] = n.split(":");
    if (!s || i === void 0) break;
    const o = Oi(s.trim());
    t[o] = i.trim();
  }
  return t;
}
const Mi = (e) => e;
function tr(e, t, r, n) {
  var s = (e & as) !== 0, i = "in", o, l = t.inert, f = t.style.overflow, a, u;
  function c() {
    return yt(() => o ??= r()(t, n?.() ?? /** @type {P} */
    {}, {
      direction: i
    }));
  }
  var d = {
    is_global: s,
    in() {
      t.inert = l, a?.abort(), a = zn(
        t,
        c(),
        u,
        1,
        () => {
          Cr(t, "introstart");
        },
        () => {
          Cr(t, "introend"), a?.abort(), a = o = void 0, t.style.overflow = f;
        }
      );
    },
    out(_) {
      {
        _?.(), o = void 0;
        return;
      }
    },
    stop: () => {
      a?.abort();
    }
  }, v = (
    /** @type {Effect & { nodes: EffectNodes }} */
    y
  );
  if ((v.nodes.t ??= []).push(d), Xt) {
    var h = s;
    if (!h) {
      for (var p = (
        /** @type {Effect | null} */
        v.parent
      ); p && p.f & Ke; )
        for (; (p = p.parent) && !(p.f & he); )
          ;
      h = !p || (p.f & Ce) !== 0;
    }
    h && hr(() => {
      ft(() => d.in());
    });
  }
}
function zn(e, t, r, n, s, i) {
  if (bs(t)) {
    var o, l = !1;
    return Pe(() => {
      if (!l) {
        var _ = t({ direction: "in" });
        o = zn(e, _, r, n, s, i);
      }
    }), {
      abort: () => {
        l = !0, o?.abort();
      },
      deactivate: () => o.deactivate(),
      reset: () => o.reset(),
      t: () => o.t()
    };
  }
  if (!t?.duration && !t?.delay)
    return s(), i(), {
      abort: re,
      deactivate: re,
      reset: re,
      t: () => n
    };
  const { delay: f = 0, css: a, tick: u, easing: c = Mi } = t;
  var d = [];
  if (u && u(0, 1), a) {
    var v = Rr(a(0, 1));
    d.push(v, v);
  }
  var h = () => 1 - n, p = e.animate(d, { duration: f, fill: "forwards" });
  return p.onfinish = () => {
    p.cancel(), s();
    var _ = 1 - n, $ = n - _, g = (
      /** @type {number} */
      t.duration * Math.abs($)
    ), C = [];
    if (g > 0) {
      var w = !1;
      if (a)
        for (var m = Math.ceil(g / 16.666666666666668), T = 0; T <= m; T += 1) {
          var M = _ + $ * c(T / m), E = Rr(a(M, 1 - M));
          C.push(E), w ||= E.overflow === "hidden";
        }
      w && (e.style.overflow = "hidden"), h = () => {
        var L = (
          /** @type {number} */
          /** @type {globalThis.Animation} */
          p.currentTime
        );
        return _ + $ * c(L / g);
      }, u && Ni(() => {
        if (p.playState !== "running") return !1;
        var L = h();
        return u(L, 1 - L), !0;
      });
    }
    p = e.animate(C, { duration: g, fill: "forwards" }), p.onfinish = () => {
      h = () => n, u?.(n, 1 - n), i();
    };
  }, {
    abort: () => {
      p && (p.cancel(), p.effect = null, p.onfinish = re);
    },
    deactivate: () => {
      i = re;
    },
    reset: () => {
    },
    t: () => h()
  };
}
function br(e, t) {
  hr(() => {
    var r = e.getRootNode(), n = (
      /** @type {ShadowRoot} */
      r.host ? (
        /** @type {ShadowRoot} */
        r
      ) : (
        /** @type {Document} */
        r.head ?? /** @type {Document} */
        r.ownerDocument.head
      )
    );
    if (!n.querySelector("#" + t.hash)) {
      const s = Ft("style");
      s.id = t.hash, s.textContent = t.code, n.appendChild(s);
    }
  });
}
function jn(e) {
  var t, r, n = "";
  if (typeof e == "string" || typeof e == "number") n += e;
  else if (typeof e == "object") if (Array.isArray(e)) {
    var s = e.length;
    for (t = 0; t < s; t++) e[t] && (r = jn(e[t])) && (n && (n += " "), n += r);
  } else for (r in e) e[r] && (n && (n += " "), n += r);
  return n;
}
function Ci() {
  for (var e, t, r = 0, n = "", s = arguments.length; r < s; r++) (e = arguments[r]) && (t = jn(e)) && (n && (n += " "), n += t);
  return n;
}
function Ri(e) {
  return typeof e == "object" ? Ci(e) : e ?? "";
}
const Lr = [...` 	
\r\f \v\uFEFF`];
function Li(e, t, r) {
  var n = e == null ? "" : "" + e;
  if (t && (n = n ? n + " " + t : t), r) {
    for (var s of Object.keys(r))
      if (r[s])
        n = n ? n + " " + s : s;
      else if (n.length)
        for (var i = s.length, o = 0; (o = n.indexOf(s, o)) >= 0; ) {
          var l = o + i;
          (o === 0 || Lr.includes(n[o - 1])) && (l === n.length || Lr.includes(n[l])) ? n = (o === 0 ? "" : n.substring(0, o)) + n.substring(l + 1) : o = l;
        }
  }
  return n === "" ? null : n;
}
function Hn(e, t, r, n, s, i) {
  var o = e.__className;
  if (N || o !== r || o === void 0) {
    var l = Li(r, n, i);
    (!N || l !== e.getAttribute("class")) && (l == null ? e.removeAttribute("class") : e.className = l), e.__className = r;
  } else if (i && s !== i)
    for (var f in i) {
      var a = !!i[f];
      (s == null || a !== !!s[f]) && e.classList.toggle(f, a);
    }
  return i;
}
const Ii = Symbol("is custom element"), Di = Symbol("is html"), Pi = ks ? "link" : "LINK";
function Fi(e, t, r, n) {
  var s = zi(e);
  N && (s[t] = e.getAttribute(t), e.nodeName === Pi) || s[t] !== (s[t] = r) && (r == null ? e.removeAttribute(t) : typeof r != "string" && ji(e).includes(t) ? e[t] = r : e.setAttribute(t, r));
}
function zi(e) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    // @ts-expect-error
    e.__attributes ??= {
      [Ii]: e.nodeName.includes("-"),
      [Di]: e.namespaceURI === zr
    }
  );
}
var Ir = /* @__PURE__ */ new Map();
function ji(e) {
  var t = e.getAttribute("is") || e.nodeName, r = Ir.get(t);
  if (r) return r;
  Ir.set(t, r = []);
  for (var n, s = e, i = Element.prototype; i !== s; ) {
    n = ps(s);
    for (var o in n)
      n[o].set && r.push(o);
    s = Hr(s);
  }
  return r;
}
function Dr(e, t) {
  return e === t || e?.[vt] === t;
}
function qn(e = {}, t, r, n) {
  var s = (
    /** @type {ComponentContext} */
    G.r
  ), i = (
    /** @type {Effect} */
    y
  );
  return hr(() => {
    var o, l;
    return dr(() => {
      o = l, l = [], ft(() => {
        e !== r(...l) && (t(e, ...l), o && Dr(r(...o), e) && t(null, ...o));
      });
    }), () => {
      let f = i;
      for (; f !== s && f.parent !== null && f.parent.f & qt; )
        f = f.parent;
      const a = () => {
        l && Dr(r(...l), e) && t(null, ...l);
      }, u = f.teardown;
      f.teardown = () => {
        a(), u?.();
      };
    };
  }), e;
}
function We(e, t, r, n) {
  var s = (r & ls) !== 0, i = (r & os) !== 0, o = (
    /** @type {V} */
    n
  ), l = !0, f = () => (l && (l = !1, o = i ? ft(
    /** @type {() => V} */
    n
  ) : (
    /** @type {V} */
    n
  )), o);
  let a;
  if (s) {
    var u = vt in e || Ur in e;
    a = qe(e, t)?.set ?? (u && t in e ? (g) => e[t] = g : void 0);
  }
  var c, d = !1;
  s ? [c, d] = Bs(() => (
    /** @type {V} */
    e[t]
  )) : c = /** @type {V} */
  e[t], c === void 0 && n !== void 0 && (c = f(), a && (Cs(), a(c)));
  var v;
  if (v = () => {
    var g = (
      /** @type {V} */
      e[t]
    );
    return g === void 0 ? f() : (l = !0, g);
  }, !(r & is))
    return v;
  if (a) {
    var h = e.$$legacy;
    return (
      /** @type {() => V} */
      function(g, C) {
        return arguments.length > 0 ? ((!C || h || d) && a(C ? v() : g), g) : v();
      }
    );
  }
  var p = !1, _ = (r & ss ? Pt : fn)(() => (p = !1, v()));
  s && b(_);
  var $ = (
    /** @type {Effect} */
    y
  );
  return (
    /** @type {() => V} */
    function(g, C) {
      if (arguments.length > 0) {
        const w = C ? b(_) : s ? je(g) : g;
        return te(_, w), p = !0, o !== void 0 && (o = w), g;
      }
      return Me && p || $.f & Z ? _.v : b(_);
    }
  );
}
function Hi(e) {
  return new qi(e);
}
class qi {
  /** @type {any} */
  #e;
  /** @type {Record<string, any>} */
  #n;
  /**
   * @param {ComponentConstructorOptions & {
   *  component: any;
   * }} options
   */
  constructor(t) {
    var r = /* @__PURE__ */ new Map(), n = (i, o) => {
      var l = /* @__PURE__ */ ar(o, !1, !1);
      return r.set(i, l), l;
    };
    const s = new Proxy(
      { ...t.props || {}, $$events: {} },
      {
        get(i, o) {
          return b(r.get(o) ?? n(o, Reflect.get(i, o)));
        },
        has(i, o) {
          return o === Ur ? !0 : (b(r.get(o) ?? n(o, Reflect.get(i, o))), Reflect.has(i, o));
        },
        set(i, o, l) {
          return te(r.get(o) ?? n(o, l), l), Reflect.set(i, o, l);
        }
      }
    );
    this.#n = (t.hydrate ? mi : In)(t.component, {
      target: t.target,
      anchor: t.anchor,
      props: s,
      context: t.context,
      intro: t.intro ?? !1,
      recover: t.recover,
      transformError: t.transformError
    }), (!t?.props?.$$host || t.sync === !1) && Se(), this.#e = s.$$events;
    for (const i of Object.keys(this.#n))
      i === "$set" || i === "$destroy" || i === "$on" || gt(this, i, {
        get() {
          return this.#n[i];
        },
        /** @param {any} value */
        set(o) {
          this.#n[i] = o;
        },
        enumerable: !0
      });
    this.#n.$set = /** @param {Record<string, any>} next */
    (i) => {
      Object.assign(s, i);
    }, this.#n.$destroy = () => {
      wi(this.#n);
    };
  }
  /** @param {Record<string, any>} props */
  $set(t) {
    this.#n.$set(t);
  }
  /**
   * @param {string} event
   * @param {(...args: any[]) => any} callback
   * @returns {any}
   */
  $on(t, r) {
    this.#e[t] = this.#e[t] || [];
    const n = (...s) => r.call(this, ...s);
    return this.#e[t].push(n), () => {
      this.#e[t] = this.#e[t].filter(
        /** @param {any} fn */
        (s) => s !== n
      );
    };
  }
  $destroy() {
    this.#n.$destroy();
  }
}
let Bn;
typeof HTMLElement == "function" && (Bn = class extends HTMLElement {
  /** The Svelte component constructor */
  $$ctor;
  /** Slots */
  $$s;
  /** @type {any} The Svelte component instance */
  $$c;
  /** Whether or not the custom element is connected */
  $$cn = !1;
  /** @type {Record<string, any>} Component props data */
  $$d = {};
  /** `true` if currently in the process of reflecting component props back to attributes */
  $$r = !1;
  /** @type {Record<string, CustomElementPropDefinition>} Props definition (name, reflected, type etc) */
  $$p_d = {};
  /** @type {Record<string, EventListenerOrEventListenerObject[]>} Event listeners */
  $$l = {};
  /** @type {Map<EventListenerOrEventListenerObject, Function>} Event listener unsubscribe functions */
  $$l_u = /* @__PURE__ */ new Map();
  /** @type {any} The managed render effect for reflecting attributes */
  $$me;
  /** @type {ShadowRoot | null} The ShadowRoot of the custom element */
  $$shadowRoot = null;
  /**
   * @param {*} $$componentCtor
   * @param {*} $$slots
   * @param {ShadowRootInit | undefined} shadow_root_init
   */
  constructor(e, t, r) {
    super(), this.$$ctor = e, this.$$s = t, r && (this.$$shadowRoot = this.attachShadow(r));
  }
  /**
   * @param {string} type
   * @param {EventListenerOrEventListenerObject} listener
   * @param {boolean | AddEventListenerOptions} [options]
   */
  addEventListener(e, t, r) {
    if (this.$$l[e] = this.$$l[e] || [], this.$$l[e].push(t), this.$$c) {
      const n = this.$$c.$on(e, t);
      this.$$l_u.set(t, n);
    }
    super.addEventListener(e, t, r);
  }
  /**
   * @param {string} type
   * @param {EventListenerOrEventListenerObject} listener
   * @param {boolean | AddEventListenerOptions} [options]
   */
  removeEventListener(e, t, r) {
    if (super.removeEventListener(e, t, r), this.$$c) {
      const n = this.$$l_u.get(t);
      n && (n(), this.$$l_u.delete(t));
    }
  }
  async connectedCallback() {
    if (this.$$cn = !0, !this.$$c) {
      let e = function(n) {
        return (s) => {
          const i = Ft("slot");
          n !== "default" && (i.name = n), U(s, i);
        };
      };
      if (await Promise.resolve(), !this.$$cn || this.$$c)
        return;
      const t = {}, r = Bi(this);
      for (const n of this.$$s)
        n in r && (n === "default" && !this.$$d.children ? (this.$$d.children = e(n), t.default = !0) : t[n] = e(n));
      for (const n of this.attributes) {
        const s = this.$$g_p(n.name);
        s in this.$$d || (this.$$d[s] = St(s, n.value, this.$$p_d, "toProp"));
      }
      for (const n in this.$$p_d)
        !(n in this.$$d) && this[n] !== void 0 && (this.$$d[n] = this[n], delete this[n]);
      this.$$c = Hi({
        component: this.$$ctor,
        target: this.$$shadowRoot || this,
        props: {
          ...this.$$d,
          $$slots: t,
          $$host: this
        }
      }), this.$$me = si(() => {
        dr(() => {
          this.$$r = !0;
          for (const n of At(this.$$c)) {
            if (!this.$$p_d[n]?.reflect) continue;
            this.$$d[n] = this.$$c[n];
            const s = St(
              n,
              this.$$d[n],
              this.$$p_d,
              "toAttribute"
            );
            s == null ? this.removeAttribute(this.$$p_d[n].attribute || n) : this.setAttribute(this.$$p_d[n].attribute || n, s);
          }
          this.$$r = !1;
        });
      });
      for (const n in this.$$l)
        for (const s of this.$$l[n]) {
          const i = this.$$c.$on(n, s);
          this.$$l_u.set(s, i);
        }
      this.$$l = {};
    }
  }
  // We don't need this when working within Svelte code, but for compatibility of people using this outside of Svelte
  // and setting attributes through setAttribute etc, this is helpful
  /**
   * @param {string} attr
   * @param {string} _oldValue
   * @param {string} newValue
   */
  attributeChangedCallback(e, t, r) {
    this.$$r || (e = this.$$g_p(e), this.$$d[e] = St(e, r, this.$$p_d, "toProp"), this.$$c?.$set({ [e]: this.$$d[e] }));
  }
  disconnectedCallback() {
    this.$$cn = !1, Promise.resolve().then(() => {
      !this.$$cn && this.$$c && (this.$$c.$destroy(), this.$$me(), this.$$c = void 0);
    });
  }
  /**
   * @param {string} attribute_name
   */
  $$g_p(e) {
    return At(this.$$p_d).find(
      (t) => this.$$p_d[t].attribute === e || !this.$$p_d[t].attribute && t.toLowerCase() === e
    ) || e;
  }
});
function St(e, t, r, n) {
  const s = r[e]?.type;
  if (t = s === "Boolean" && typeof t != "boolean" ? t != null : t, !n || !r[e])
    return t;
  if (n === "toAttribute")
    switch (s) {
      case "Object":
      case "Array":
        return t == null ? null : JSON.stringify(t);
      case "Boolean":
        return t ? "" : null;
      case "Number":
        return t ?? null;
      default:
        return t;
    }
  else
    switch (s) {
      case "Object":
      case "Array":
        return t && JSON.parse(t);
      case "Boolean":
        return t;
      case "Number":
        return t != null ? +t : t;
      default:
        return t;
    }
}
function Bi(e) {
  const t = {};
  return e.childNodes.forEach((r) => {
    t[
      /** @type {Element} node */
      r.slot || "default"
    ] = !0;
  }), t;
}
function mr(e, t, r, n, s, i) {
  let o = class extends Bn {
    constructor() {
      super(e, r, s), this.$$p_d = t;
    }
    static get observedAttributes() {
      return At(t).map(
        (l) => (t[l].attribute || l).toLowerCase()
      );
    }
  };
  return At(t).forEach((l) => {
    gt(o.prototype, l, {
      get() {
        return this.$$c && l in this.$$c ? this.$$c[l] : this.$$d[l];
      },
      set(f) {
        f = St(l, f, t), this.$$d[l] = f;
        var a = this.$$c;
        if (a) {
          var u = qe(a, l)?.get;
          u ? a[l] = f : a.$set({ [l]: f });
        }
      }
    });
  }), n.forEach((l) => {
    gt(o.prototype, l, {
      get() {
        return this.$$c?.[l];
      }
    });
  }), e.element = /** @type {any} */
  o, o;
}
const tt = rn(null), Un = rn({}), Ui = (e) => e;
function Vn(e) {
  const t = e - 1;
  return t * t * t + 1;
}
function Pr(e) {
  const t = typeof e == "string" && e.match(/^\s*(-?[\d.]+)([^\s]*)\s*$/);
  return t ? [parseFloat(t[1]), t[2] || "px"] : [
    /** @type {number} */
    e,
    "px"
  ];
}
function Vi(e, { delay: t = 0, duration: r = 400, easing: n = Ui } = {}) {
  const s = +getComputedStyle(e).opacity;
  return {
    delay: t,
    duration: r,
    easing: n,
    css: (i) => `opacity: ${i * s}`
  };
}
function Yi(e, { delay: t = 0, duration: r = 400, easing: n = Vn, x: s = 0, y: i = 0, opacity: o = 0 } = {}) {
  const l = getComputedStyle(e), f = +l.opacity, a = l.transform === "none" ? "" : l.transform, u = f * (1 - o), [c, d] = Pr(s), [v, h] = Pr(i);
  return {
    delay: t,
    duration: r,
    easing: n,
    css: (p, _) => `
			transform: ${a} translate(${(1 - p) * c}${d}, ${(1 - p) * v}${h});
			opacity: ${f - u * _}`
  };
}
function Wi(e, { delay: t = 0, duration: r = 400, easing: n = Vn, start: s = 0, opacity: i = 0 } = {}) {
  const o = getComputedStyle(e), l = +o.opacity, f = o.transform === "none" ? "" : o.transform, a = 1 - s, u = l * (1 - i);
  return {
    delay: t,
    duration: r,
    easing: n,
    css: (c, d) => `
			transform: ${f} scale(${1 - a * d});
			opacity: ${l - u * d}
		`
  };
}
function Yn(e) {
  const t = e - 1;
  return t * t * t + 1;
}
var Gi = /* @__PURE__ */ ae('<a class="src-link svelte-3iukgs" target="_blank" rel="noopener noreferrer"> <span class="src-ext svelte-3iukgs">↗</span></a>'), Ki = /* @__PURE__ */ ae('<span class="svelte-3iukgs"> </span>'), Ji = /* @__PURE__ */ ae('<span class="src-vintage svelte-3iukgs"> </span>'), Zi = /* @__PURE__ */ ae('<li><span class="src-num svelte-3iukgs"> </span> <div class="svelte-3iukgs"><!> <span class="src-id svelte-3iukgs"> </span> <!></div></li>'), Xi = /* @__PURE__ */ ae('<div class="src-h svelte-3iukgs">Sources</div> <ol class="svelte-3iukgs"></ol>', 1);
const Qi = {
  hash: "svelte-3iukgs",
  code: `:host {display:block;border-top:1px solid var(--line, #e5e7eb);background:var(--bg-soft, #f5f7fb);padding:12px 16px 14px;}:host(:not(:has(ol))) {display:none;}.src-h.svelte-3iukgs {font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.10em;color:var(--text-muted, #6b7280);margin:0 0 8px;}ol.svelte-3iukgs {margin:0;padding:0;list-style:none;display:grid;gap:6px;font-size:11.5px;line-height:1.45;}li.svelte-3iukgs {display:grid;grid-template-columns:22px 1fr;gap:8px;align-items:baseline;padding:4px 6px;border-radius:3px;cursor:pointer;transition:background 0.15s;}li.svelte-3iukgs:hover, li.hl.svelte-3iukgs {background:rgba(22, 66, 223, 0.10);}li.hl.svelte-3iukgs {
    /* Brief pulse each time a chip selects this row. */
    animation: svelte-3iukgs-pulse 360ms cubic-bezier(.2,.7,.3,1);}
  @keyframes svelte-3iukgs-pulse {
    0%   { box-shadow: 0 0 0 0   rgba(22, 66, 223, 0.35); }
    60%  { box-shadow: 0 0 0 6px rgba(22, 66, 223, 0.00); }
    100% { box-shadow: 0 0 0 0   rgba(22, 66, 223, 0.00); }
  }.src-num.svelte-3iukgs {font-family:var(--mono, monospace);font-size:10.5px;font-weight:700;color:var(--nyc-blue, #1642DF);text-align:right;}.src-link.svelte-3iukgs {color:var(--text, #111);text-decoration:none;border-bottom:1px dotted var(--text-muted, #6b7280);}.src-link.svelte-3iukgs:hover {color:var(--nyc-blue, #1642DF);border-bottom-color:var(--nyc-blue, #1642DF);}.src-ext.svelte-3iukgs {font-size:9.5px;color:var(--text-faint, #9ca3af);margin-left:2px;vertical-align:super;}.src-vintage.svelte-3iukgs {display:block;color:var(--text-muted, #6b7280);font-size:9.5px;margin-top:2px;}.src-id.svelte-3iukgs {display:inline-block;font-family:var(--mono, monospace);font-size:9.5px;color:var(--text-faint, #9ca3af);margin-left:6px;}`
};
function el(e, t) {
  It(t, !0), br(e, Qi);
  const r = () => Vt(Un, "$citeIndex", s), n = () => Vt(tt, "$highlightedDocId", s), [s, i] = nn();
  let o = We(t, "labels", 23, () => ({})), l = We(t, "urls", 23, () => ({})), f = We(t, "vintages", 23, () => ({})), a = /* @__PURE__ */ Le(() => Object.entries(r() || {}).sort((_, $) => _[1] - $[1])), u = /* @__PURE__ */ Le(n);
  var c = {
    get labels() {
      return o();
    },
    set labels(_ = {}) {
      o(_), Se();
    },
    get urls() {
      return l();
    },
    set urls(_ = {}) {
      l(_), Se();
    },
    get vintages() {
      return f();
    },
    set vintages(_ = {}) {
      f(_), Se();
    }
  }, d = Ln(), v = Kt(d);
  {
    var h = (_) => {
      var $ = Xi(), g = Kt($), C = $e(g, 2);
      Pn(C, 21, () => b(a), ([w, m]) => w, (w, m) => {
        var T = /* @__PURE__ */ Le(() => ws(b(m), 2));
        let M = () => b(T)[0], E = () => b(T)[1];
        const L = /* @__PURE__ */ Le(() => l()[M()]), q = /* @__PURE__ */ Le(() => o()[M()] || M()), O = /* @__PURE__ */ Le(() => f()[M()]);
        var k = Zi();
        let I;
        var X = B(k), Wn = B(X);
        F(X);
        var wr = $e(X, 2), yr = B(wr);
        {
          var Gn = (pe) => {
            var K = Gi(), ut = B(K);
            Vr(), F(K), Te(() => {
              Fi(K, "href", b(L)), fe(ut, `${b(q) ?? ""} `);
            }), Nr("click", K, (Qn) => Qn.stopPropagation()), U(pe, K);
          }, Kn = (pe) => {
            var K = Ki(), ut = B(K, !0);
            F(K), Te(() => fe(ut, b(q))), U(pe, K);
          };
          Ye(yr, (pe) => {
            b(L) ? pe(Gn) : pe(Kn, -1);
          });
        }
        var zt = $e(yr, 2), Jn = B(zt, !0);
        F(zt);
        var Zn = $e(zt, 2);
        {
          var Xn = (pe) => {
            var K = Ji(), ut = B(K, !0);
            F(K), Te(() => fe(ut, b(O))), U(pe, K);
          };
          Ye(Zn, (pe) => {
            b(O) && pe(Xn);
          });
        }
        F(wr), F(k), Te(() => {
          I = Hn(k, 1, "svelte-3iukgs", null, I, { hl: M() === b(u) }), fe(Wn, `[${E() ?? ""}]`), fe(Jn, M());
        }), hi("mouseenter", k, () => tt.set(M())), Nr("click", k, () => tt.set(b(u) === M() ? null : M())), tr(1, k, () => Wi, () => ({ start: 0.96, duration: 220, easing: Yn })), U(w, k);
      }), F(C), tr(1, g, () => Vi, () => ({ duration: 200 })), U(_, $);
    };
    Ye(v, (_) => {
      b(a).length && _(h);
    });
  }
  U(e, d);
  var p = Dt(c);
  return i(), p;
}
di(["click"]);
customElements.define("r-sources-footer", mr(
  el,
  {
    labels: { type: "Object" },
    urls: { type: "Object" },
    vintages: { type: "Object" }
  },
  [],
  [],
  { mode: "open" }
));
var tl = /* @__PURE__ */ ae('<div class="rsum-p svelte-5ir0b" style="color:var(--text-muted, #6b7280)">Waiting for content…</div>'), rl = /* @__PURE__ */ ae('<div class="svelte-5ir0b"></div>');
const nl = {
  hash: "svelte-5ir0b",
  code: `:host {display:block;}
  /* The host-level styles for typography, .cite, etc. live in the parent
     stylesheet and target #paragraph descendants — they pierce shadow DOM
     for inline-styled markup we don't ship here. The .rsum-* classes are
     wired in the global stylesheet. We intentionally don't restate them. */:host(.streaming)::after,
  :host([streaming])::after {content:"▋";display:inline-block;color:var(--nyc-blue, #1642DF);margin-left:2px;
    animation: svelte-5ir0b-caret 0.9s steps(1) infinite;}
  @keyframes svelte-5ir0b-caret { 50% { opacity: 0; } }`
};
function sl(e, t) {
  It(t, !0), br(e, nl);
  const r = () => Vt(tt, "$highlightedDocId", n), [n, s] = nn();
  let i = We(t, "text", 7, ""), o = We(t, "streaming", 7, !1), l = We(t, "sourceLabels", 23, () => ({}));
  const f = (w) => String(w ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  function a(w) {
    const m = w.split(`
`), T = [];
    let M = [], E = [];
    const L = () => {
      if (!M.length) return;
      const k = f(M.join(" ").trim()).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      k && T.push(`<p class="rsum-p">${k}</p>`), M = [];
    }, q = () => {
      if (!E.length) return;
      const k = E.map((I) => `<li>${f(I.trim()).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")}</li>`).join("");
      T.push(`<ul class="rsum-list">${k}</ul>`), E = [];
    }, O = [];
    for (const k of m)
      if (k.trim().startsWith("- ") && k.includes(" - ", 2)) {
        const I = k.split(/(?:^|(?<=\.\s))\s*-\s+/g).filter((X) => X.trim());
        for (const X of I) O.push("- " + X.trim());
      } else
        O.push(k);
    for (const k of O) {
      const I = k.match(/^\s*\*\*([A-Z][A-Za-z\s/]+)\.\*\*\s*$/);
      I ? (L(), q(), T.push(`<h4 class="rsum-h">${f(I[1])}</h4>`)) : /^\s*[-*]\s+/.test(k) ? (L(), E.push(k.replace(/^\s*[-*]\s+/, ""))) : (q(), M.push(k));
    }
    return L(), q(), T.join("");
  }
  function u(w, m) {
    return w.replace(/\[([a-z0-9_]+)\]/gi, (T, M) => {
      const E = M.toLowerCase();
      m[E] == null && (m[E] = Object.keys(m).length + 1);
      const L = m[E], q = l()[E] || E;
      return `<span class="cite" data-src-id="${E}" data-src-n="${L}" title="${q.replace(/"/g, "&quot;")} — click to highlight">${L}</span>`;
    });
  }
  let c = /* @__PURE__ */ Le(() => {
    if (!i()) return "";
    const w = {}, m = a(i()), T = u(m, w);
    return queueMicrotask(() => Un.set({ ...w })), T;
  }), d, v = /* @__PURE__ */ Le(r);
  mn(() => {
    b(c), b(v), d && ui().then(() => {
      d.querySelectorAll(".cite").forEach((m) => {
        const T = m.dataset.srcId;
        T && (m.classList.toggle("hl", T === b(v)), !m.dataset.bound && (m.dataset.bound = "1", m.addEventListener("mouseenter", () => tt.set(T)), m.addEventListener("click", (M) => {
          M.stopPropagation(), tt.update((E) => E === T ? null : T);
        })));
      });
    });
  });
  var h = {
    get text() {
      return i();
    },
    set text(w = "") {
      i(w), Se();
    },
    get streaming() {
      return o();
    },
    set streaming(w = !1) {
      o(w), Se();
    },
    get sourceLabels() {
      return l();
    },
    set sourceLabels(w = {}) {
      l(w), Se();
    }
  }, p = Ln(), _ = Kt(p);
  {
    var $ = (w) => {
      var m = tl();
      U(w, m);
    }, g = (w) => {
      var m = rl();
      Si(m, () => b(c), !0), F(m), qn(m, (T) => d = T, () => d), U(w, m);
    };
    Ye(_, (w) => {
      i() ? w(g, -1) : w($);
    });
  }
  U(e, p);
  var C = Dt(h);
  return s(), C;
}
customElements.define("r-briefing", mr(
  sl,
  {
    text: { type: "String" },
    streaming: { reflect: !0, type: "Boolean" },
    sourceLabels: { type: "Object" }
  },
  [],
  [],
  { mode: "open" }
));
var il = /* @__PURE__ */ ae('<span class="time svelte-c4g9ik"> </span>'), ll = /* @__PURE__ */ ae('<div class="result svelte-c4g9ik"> </div>'), ol = /* @__PURE__ */ ae('<div class="result svelte-c4g9ik" style="color:var(--nyc-scarlet, #b80000)"> </div>'), al = /* @__PURE__ */ ae('<li><span class="icon svelte-c4g9ik"> </span> <div><div class="label svelte-c4g9ik"> </div> <div class="meta svelte-c4g9ik"> </div></div> <!> <!> <!></li>'), fl = /* @__PURE__ */ ae('<ol id="steps-list" class="svelte-c4g9ik"></ol>');
const ul = {
  hash: "svelte-c4g9ik",
  code: ":host {display:block;}ol.svelte-c4g9ik {list-style:none;margin:0;padding:4px 0;font-size:12.5px;}li.svelte-c4g9ik {display:grid;grid-template-columns:18px 1fr auto;gap:10px;padding:7px 14px;border-bottom:1px solid var(--line, #e5e7eb);align-items:baseline;}li.svelte-c4g9ik:last-child {border-bottom:0;}.icon.svelte-c4g9ik {font-weight:700;font-size:14px;line-height:1;}.running.svelte-c4g9ik .icon:where(.svelte-c4g9ik) {color:var(--nyc-blue, #1642DF);}.ok.svelte-c4g9ik      .icon:where(.svelte-c4g9ik) {color:var(--good, #1a8754);}.err.svelte-c4g9ik     .icon:where(.svelte-c4g9ik) {color:var(--nyc-scarlet, #b80000);}.label.svelte-c4g9ik  {color:var(--text, #111);font-weight:500;}.meta.svelte-c4g9ik   {color:var(--text-muted, #6b7280);font-size:11px;}.time.svelte-c4g9ik   {font-family:var(--mono, monospace);color:var(--text-faint, #9ca3af);font-size:11.5px;}.running.svelte-c4g9ik {background:rgba(22, 66, 223, 0.04);}.result.svelte-c4g9ik {grid-column:2 / -1;color:var(--text-muted, #6b7280);font-size:11px;font-family:var(--mono, monospace);margin-top:3px;word-break:break-word;line-height:1.4;}"
};
function cl(e, t) {
  It(t, !0), br(e, ul);
  let r = We(t, "stepLabels", 23, () => ({})), n = /* @__PURE__ */ me(je([]));
  $i(() => {
    const c = s?.getRootNode()?.host;
    c && (c.pushStep = (d) => {
      te(n, [...b(n), d], !0);
    }, c.clear = () => {
      te(n, [], !0);
    });
  });
  let s;
  function i(c) {
    return c.ok === !0 ? "ok" : c.ok === !1 ? "err" : "running";
  }
  function o(c) {
    return c.ok === !0 ? "✓" : c.ok === !1 ? "✗" : "○";
  }
  function l(c) {
    return r()[c.step] && r()[c.step][0] || c.step;
  }
  function f(c) {
    return r()[c.step] && r()[c.step][1] || "";
  }
  var a = {
    get stepLabels() {
      return r();
    },
    set stepLabels(c = {}) {
      r(c), Se();
    }
  }, u = fl();
  return Pn(u, 21, () => b(n), ki, (c, d) => {
    var v = al(), h = B(v), p = B(h, !0);
    F(h);
    var _ = $e(h, 2), $ = B(_), g = B($, !0);
    F($);
    var C = $e($, 2), w = B(C, !0);
    F(C), F(_);
    var m = $e(_, 2);
    {
      var T = (O) => {
        var k = il(), I = B(k);
        F(k), Te(() => fe(I, `${b(d).elapsed_s ?? ""}s`)), U(O, k);
      };
      Ye(m, (O) => {
        b(d).elapsed_s != null && O(T);
      });
    }
    var M = $e(m, 2);
    {
      var E = (O) => {
        var k = ll(), I = B(k, !0);
        F(k), Te((X) => fe(I, X), [() => JSON.stringify(b(d).result)]), U(O, k);
      };
      Ye(M, (O) => {
        b(d).result && O(E);
      });
    }
    var L = $e(M, 2);
    {
      var q = (O) => {
        var k = ol(), I = B(k, !0);
        F(k), Te(() => fe(I, b(d).err)), U(O, k);
      };
      Ye(L, (O) => {
        b(d).err && O(q);
      });
    }
    F(v), Te(
      (O, k, I, X) => {
        Hn(v, 1, O, "svelte-c4g9ik"), fe(p, k), fe(g, I), fe(w, X);
      },
      [
        () => Ri(i(b(d))),
        () => o(b(d)),
        () => l(b(d)),
        () => f(b(d))
      ]
    ), tr(1, v, () => Yi, () => ({ y: -8, duration: 220, easing: Yn })), U(c, v);
  }), F(u), qn(u, (c) => s = c, () => s), U(e, u), Dt(a);
}
customElements.define("r-trace", mr(cl, { stepLabels: { type: "Object" } }, [], [], { mode: "open" }));
export {
  Un as citeIndex,
  tt as highlightedDocId
};
//# sourceMappingURL=riprap.js.map
