"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { addEvent } from "@/services/api";
import { getCaptureState, isCapturing, recordEvent } from "@/services/captureStore";
import { useCaptureState } from "@/hooks/useCaptureState";

interface Invoice {
  id: string;
  supplier: string;
  amount: number;
  costCenter: string;
  assetNumber: string;
}

const INITIAL: Invoice = {
  id: "INV-4471",
  supplier: "Northwind Industrial",
  amount: 7200,
  costCenter: "OPEX",
  assetNumber: "",
};

export default function DemoErpPage() {
  const [invoice, setInvoice] = useState<Invoice>(INITIAL);
  const [history, setHistory] = useState(false);
  const [saved, setSaved] = useState(false);
  const [lastEvent, setLastEvent] = useState<string>("—");
  const capture = useCaptureState();

  const emit = async (type: string, data: Record<string, unknown>) => {
    const st = getCaptureState();
    const timestamp = Date.now();
    if (st.sessionId && isCapturing()) {
      try {
        await addEvent(st.sessionId, {
          client_event_id: crypto.randomUUID(),
          timestamp_ms: timestamp,
          source: "demo_erp",
          type,
          data,
        });
      } catch {
        // ignore demo network errors
      }
      recordEvent(timestamp);
    }
    setLastEvent(`${type} @ ${new Date(timestamp).toLocaleTimeString()}`);
  };

  useEffect(() => {
    const t = setTimeout(() => {
      void emit("invoice_opened", {
        invoice_id: INITIAL.id,
        amount: INITIAL.amount,
        supplier: INITIAL.supplier,
      });
    }, 0);
    return () => clearTimeout(t);
  }, []);

  const viewHistory = () => {
    setHistory(true);
    void emit("supplier_history_viewed", { supplier: invoice.supplier, invoice_id: invoice.id });
  };

  const changeCostCenter = (value: string) => {
    const old = invoice.costCenter;
    setInvoice((i) => ({ ...i, costCenter: value }));
    void emit("field_changed", {
      entity: "invoice",
      field: "cost_center",
      old_value: old,
      new_value: value,
      invoice_id: invoice.id,
    });
  };

  const enterAssetNumber = (value: string) => {
    setInvoice((i) => ({ ...i, assetNumber: value }));
    if (value) {
      void emit("asset_number_entered", { field: "asset_number", new_value: value, invoice_id: invoice.id });
    }
  };

  const save = () => {
    void emit("save_attempted", {
      invoice_id: invoice.id,
      cost_center: invoice.costCenter,
      asset_number: invoice.assetNumber,
      amount: invoice.amount,
    });
    setSaved(true);
  };

  return (
    <main className="min-h-screen bg-slate-100 p-6 text-slate-900">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Fictional Demo ERP</p>
          <h1 className="text-2xl font-semibold">Invoice Processing</h1>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`rounded-full px-3 py-1 text-xs ${
              isCapturing() ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-600"
            }`}
          >
            {capture.status}
          </span>
          <Link href="/expert" className="text-sm underline">
            Back to capture
          </Link>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <section className="rounded-xl border bg-white p-6">
          <h2 className="text-lg font-semibold">Invoice {invoice.id}</h2>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-slate-500">Supplier</dt>
              <dd className="mt-1 font-medium">{invoice.supplier}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Amount</dt>
              <dd className="mt-1 font-medium">${invoice.amount.toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Cost center</dt>
              <dd className="mt-1">
                <select
                  value={invoice.costCenter}
                  onChange={(e) => changeCostCenter(e.target.value)}
                  className="rounded border px-2 py-1"
                >
                  <option value="OPEX">OPEX</option>
                  <option value="CAPEX">CAPEX</option>
                </select>
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Asset number</dt>
              <dd className="mt-1">
                <input
                  value={invoice.assetNumber}
                  onChange={(e) => enterAssetNumber(e.target.value)}
                  placeholder="A-1001"
                  className="rounded border px-2 py-1"
                />
              </dd>
            </div>
          </dl>
          <div className="mt-6 flex gap-3">
            <button onClick={viewHistory} className="rounded-lg border px-4 py-2 text-sm">
              View supplier history
            </button>
            <button onClick={save} className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">
              Save invoice
            </button>
          </div>
          {saved && <p className="mt-4 text-sm text-emerald-700">Saved to local demo state.</p>}
        </section>

        <aside className="rounded-xl border bg-white p-6">
          <h2 className="text-lg font-semibold">Activity</h2>
          <p className="mt-2 text-sm text-slate-500">Last event: {lastEvent}</p>
          <p className="mt-2 text-xs text-slate-500">
            Events are emitted only while capture is active. This page is safe to share as your screen.
          </p>
          {history && (
            <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
              <p className="font-medium">Supplier history</p>
              <p className="mt-1 text-slate-600">Previous invoices: 3 • Last invoice: $2,100 (OPEX)</p>
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}
