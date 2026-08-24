import { useEffect, useMemo, useState } from "react";
import "./App.css";

const CONFIGURED_API_URL = (
  import.meta.env.VITE_API_URL || ""
)
  .trim()
  .replace(/\/$/, "");

// During `npm run dev`, keep browser requests same-origin and let
// Vite proxy /api calls to FastAPI. This completely removes local
// browser CORS dependence, even when Vite falls back to 5174/5175.
const API_URL = import.meta.env.DEV
  ? ""
  : CONFIGURED_API_URL;

const NAV_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "incidents", label: "Incidents" },
  { id: "complaints", label: "Complaints" },
  { id: "lab", label: "Reliability Lab" },
  { id: "audit", label: "Audit Trail" },
];

function statusTone(status) {
  if (status === "INVESTIGATED") return "danger";
  if (status === "RECOVERED") return "success";
  if (status === "HEALTHY") return "success";
  return "warning";
}

function statusLabel(status) {
  if (status === "INVESTIGATED") return "ACTIVE INCIDENT";
  if (status === "RECOVERED") return "RECOVERED";
  if (status === "HEALTHY") return "HEALTHY";
  return status || "PENDING";
}


function incidentPhaseCopy(status) {
  if (status === "RECOVERED") {
    return {
      title: "Incident resolved",
      detail:
        "Merchant and provider state have converged. Historical failure evidence remains preserved for audit and reproduction.",
      tone: "recovered",
    };
  }

  if (status === "INVESTIGATED") {
    return {
      title: "Active state divergence",
      detail:
        "Provider and merchant truth currently disagree. Investigation and verification are required.",
      tone: "active",
    };
  }

  if (status === "HEALTHY") {
    return {
      title: "Payment state consistent",
      detail:
        "Provider and merchant state are currently converged.",
      tone: "healthy",
    };
  }

  return {
    title: "Evidence pending",
    detail:
      "PayTrace is waiting for enough payment evidence to classify this order.",
    tone: "pending",
  };
}

function formatMoney(amount) {
  if (amount == null) return "—";
  return `₹${(amount / 100).toLocaleString("en-IN")}`;
}

function formatTime(value) {
  if (!value) return "—";

  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function shorten(value, size = 18) {
  if (!value) return "—";
  if (value.length <= size) return value;
  return `${value.slice(0, size)}…`;
}


function AnimatedNumber({
  value,
  suffix = "",
  duration = 850,
}) {
  const numericValue = Number(value);
  const isNumeric =
    value !== "" &&
    value !== null &&
    value !== undefined &&
    Number.isFinite(numericValue);

  const [displayValue, setDisplayValue] = useState(
    isNumeric ? 0 : value
  );

  useEffect(() => {
    if (!isNumeric) {
      setDisplayValue(value);
      return;
    }

    const reduceMotion =
      window.matchMedia?.(
        "(prefers-reduced-motion: reduce)"
      )?.matches;

    if (reduceMotion) {
      setDisplayValue(numericValue);
      return;
    }

    let frameId;
    let startTime;

    const decimalPlaces = String(value).includes(".")
      ? Math.min(
          1,
          String(value).split(".")[1]?.length || 0
        )
      : 0;

    function tick(timestamp) {
      if (!startTime) startTime = timestamp;

      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = numericValue * eased;

      setDisplayValue(
        decimalPlaces
          ? Number(next.toFixed(decimalPlaces))
          : Math.round(next)
      );

      if (progress < 1) {
        frameId = requestAnimationFrame(tick);
      } else {
        setDisplayValue(numericValue);
      }
    }

    frameId = requestAnimationFrame(tick);

    return () => {
      if (frameId) cancelAnimationFrame(frameId);
    };
  }, [value, duration, isNumeric, numericValue]);

  return (
    <>
      {isNumeric ? displayValue : value}
      {suffix}
    </>
  );
}


function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const DEMO_STEP_TEMPLATE = [
  {
    id: "fault",
    label: "Inject webhook fault",
    detail: "Enable controlled merchant webhook-processing failure.",
  },
  {
    id: "payment",
    label: "Complete test payment",
    detail: "Create and complete a ₹499 Razorpay Test Mode payment.",
  },
  {
    id: "detect",
    label: "Detect divergence",
    detail: "Wait for provider success + merchant-state mismatch evidence.",
  },
  {
    id: "diagnose",
    label: "Diagnose root cause",
    detail: "Confirm WEBHOOK_HANDLER_FAILURE from deterministic evidence.",
  },
  {
    id: "reproduce",
    label: "Reproduce failure",
    detail: "Replay the failure signature in the isolated reliability lab.",
  },
  {
    id: "verify",
    label: "Verify fix",
    detail: "Run regression verification against the confirmed hypothesis.",
  },
];

function App() {
  const [view, setView] = useState("overview");
  const [dashboard, setDashboard] = useState(null);
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [faultEnabled, setFaultEnabled] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState("");
  const [lastPaymentOrder, setLastPaymentOrder] = useState(null);
  const [actionStatus, setActionStatus] = useState("");
  const [complaints, setComplaints] = useState([]);
  const [complaintResult, setComplaintResult] = useState(null);
  const [complaintSubmitting, setComplaintSubmitting] = useState(false);
  const [reliabilitySuite, setReliabilitySuite] = useState(null);
  const [suiteRunning, setSuiteRunning] = useState(false);
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoOrderId, setDemoOrderId] = useState(null);
  const [demoVerdict, setDemoVerdict] = useState(null);
  const [demoError, setDemoError] = useState("");
  const [exportingReport, setExportingReport] = useState(false);
  const [demoSteps, setDemoSteps] = useState(
    DEMO_STEP_TEMPLATE.map((step) => ({
      ...step,
      status: "WAITING",
      result: "",
    }))
  );

  const recentOrders = dashboard?.recent_orders || [];

  async function loadDashboard() {
    setLoading(true);

    try {
      const [
        summaryResponse,
        faultResponse,
        suiteResponse,
      ] = await Promise.all([
        fetch(`${API_URL}/api/dashboard/summary`),
        fetch(`${API_URL}/api/faults`),
        fetch(`${API_URL}/api/reliability/suite`),
      ]);

      const summaryData = await summaryResponse.json();
      const faultData = await faultResponse.json();
      const suiteData = await suiteResponse.json();

      setDashboard(summaryData);
      setReliabilitySuite(
        suiteData?.latest_run || null
      );
      setFaultEnabled(
        Boolean(
          faultData?.faults?.webhook_processing_failure
        )
      );

      if (
        !selectedOrderId &&
        summaryData.recent_orders?.length
      ) {
        const demoOrder =
          summaryData.recent_orders.find(
            (order) => order.fix_verification === "PASS"
          ) ||
          summaryData.recent_orders.find(
            (order) => order.reproduction === "REPRODUCED"
          ) ||
          summaryData.recent_orders.find(
            (order) => order.status === "INVESTIGATED"
          ) ||
          summaryData.recent_orders[0];

        setSelectedOrderId(demoOrder.order_id);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  async function loadReport(orderId) {
    if (!orderId) return;

    setReportLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/api/orders/${orderId}/report`
      );

      if (!response.ok) {
        throw new Error("Unable to load incident report");
      }

      setReport(await response.json());
    } catch (error) {
      console.error(error);
      setReport(null);
    } finally {
      setReportLoading(false);
    }
  }

  async function loadComplaints() {
    try {
      const response = await fetch(
        `${API_URL}/api/complaints?limit=20`
      );

      if (!response.ok) return;

      const data = await response.json();
      setComplaints(data.complaints || []);
    } catch (error) {
      console.error(error);
    }
  }

  async function submitComplaint(payload) {
    setComplaintSubmitting(true);

    try {
      const response = await fetch(
        `${API_URL}/api/complaints`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Complaint intake failed"
        );
      }

      setComplaintResult(data);
      await loadComplaints();

      return data;
    } finally {
      setComplaintSubmitting(false);
    }
  }

  useEffect(() => {
    loadDashboard();
    loadComplaints();
  }, []);

  useEffect(() => {
    if (selectedOrderId) {
      loadReport(selectedOrderId);
    }
  }, [selectedOrderId]);

  function resetDemoState() {
    setDemoOrderId(null);
    setDemoVerdict(null);
    setDemoError("");
    setDemoSteps(
      DEMO_STEP_TEMPLATE.map((step) => ({
        ...step,
        status: "WAITING",
        result: "",
      }))
    );
  }

  function updateDemoStep(id, status, result = "") {
    setDemoSteps((current) =>
      current.map((step) =>
        step.id === id
          ? {
              ...step,
              status,
              result,
            }
          : step
      )
    );
  }

  async function fetchOrderReport(orderId) {
    const response = await fetch(
      `${API_URL}/api/orders/${orderId}/report`
    );

    if (!response.ok) {
      return null;
    }

    return response.json();
  }

  async function waitForDivergence(orderId) {
    let lastReport = null;

    // Provider state may be available immediately after payment verification,
    // while the webhook evidence can arrive a few seconds later.
    for (let attempt = 0; attempt < 18; attempt += 1) {
      lastReport = await fetchOrderReport(orderId);

      if (
        lastReport?.analysis?.state_divergence ||
        lastReport?.investigation?.status === "INVESTIGATED"
      ) {
        return lastReport;
      }

      await wait(850);
    }

    return lastReport;
  }

  async function waitForExpectedDiagnosis(orderId) {
    let lastReport = null;

    // Do not fail the demo just because an early investigation temporarily
    // reports WEBHOOK_NOT_RECEIVED / PENDING_ASYNC_PROCESSING before the
    // Razorpay webhook reaches the local tunnel.
    for (let attempt = 0; attempt < 35; attempt += 1) {
      lastReport = await fetchOrderReport(orderId);

      const hypothesis =
        lastReport?.investigation
          ?.primary_hypothesis?.code;

      if (
        hypothesis ===
        "WEBHOOK_HANDLER_FAILURE"
      ) {
        return {
          confirmed: true,
          report: lastReport,
        };
      }

      await wait(1000);
    }

    return {
      confirmed: false,
      report: lastReport,
    };
  }


  async function runPayTraceDemo() {
    if (demoRunning) return;

    resetDemoState();
    setDemoRunning(true);

    let faultWasEnabled = false;

    try {
      // 1. Enable controlled fault.
      updateDemoStep("fault", "RUNNING");

      const faultResponse = await fetch(
        `${API_URL}/api/faults/webhook/enable`,
        {
          method: "POST",
        }
      );

      if (!faultResponse.ok) {
        throw new Error(
          "Could not enable the controlled webhook fault."
        );
      }

      faultWasEnabled = true;
      setFaultEnabled(true);

      updateDemoStep(
        "fault",
        "PASS",
        "Controlled webhook-processing failure enabled."
      );

      // 2. Create a Razorpay test order.
      updateDemoStep(
        "payment",
        "RUNNING",
        "Creating Razorpay test order…"
      );

      const orderResponse = await fetch(
        `${API_URL}/api/orders`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            amount: 49900,
          }),
        }
      );

      const orderData = await orderResponse.json();

      if (!orderResponse.ok) {
        throw new Error(
          orderData.detail ||
            "Demo order creation failed."
        );
      }

      const orderId = orderData.order.id;
      setDemoOrderId(orderId);
      setLastPaymentOrder(orderId);

      // Razorpay Checkout still requires explicit user interaction.
      await new Promise((resolve, reject) => {
        const options = {
          key: orderData.key_id,
          amount: orderData.order.amount,
          currency: orderData.order.currency,
          name: "PayTrace AI",
          description: "Buildathon reliability demo",
          order_id: orderId,

          handler: async function (response) {
            try {
              const verifyResponse = await fetch(
                `${API_URL}/api/payments/verify`,
                {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                    razorpay_payment_id:
                      response.razorpay_payment_id,
                    razorpay_order_id:
                      response.razorpay_order_id,
                    razorpay_signature:
                      response.razorpay_signature,
                  }),
                }
              );

              const verification =
                await verifyResponse.json();

              if (!verifyResponse.ok) {
                throw new Error(
                  verification.detail ||
                    "Payment verification failed."
                );
              }

              updateDemoStep(
                "payment",
                "PASS",
                "₹499 test payment verified."
              );

              resolve(response);
            } catch (error) {
              reject(error);
            }
          },

          modal: {
            ondismiss: function () {
              reject(
                new Error(
                  "Razorpay Checkout was closed before the demo payment completed."
                )
              );
            },
          },

          prefill: {
            name: "PayTrace Demo",
            email: "demo@paytrace.dev",
            contact: "9999999999",
          },

          notes: {
            project: "PayTrace AI",
            mode: "buildathon-demo",
          },

          theme: {
            color: "#635bff",
          },
        };

        const checkout =
          new window.Razorpay(options);

        checkout.on(
          "payment.failed",
          (response) => {
            reject(
              new Error(
                response?.error?.description ||
                  "Razorpay test payment failed."
              )
            );
          }
        );

        checkout.open();
      });

      // 3. Detect state divergence first.
      updateDemoStep(
        "detect",
        "RUNNING",
        "Waiting for provider/merchant state divergence…"
      );

      const divergenceReport =
        await waitForDivergence(orderId);

      if (
        !divergenceReport?.analysis?.state_divergence &&
        divergenceReport?.investigation?.status !==
          "INVESTIGATED"
      ) {
        throw new Error(
          "PayTrace did not observe provider/merchant state divergence within the demo window."
        );
      }

      updateDemoStep(
        "detect",
        "PASS",
        `Provider paid while merchant remained ${divergenceReport?.order?.merchant_state || "non-PAID"}.`
      );

      // 4. Diagnosis is intentionally a separate wait. Razorpay webhook
      // delivery through the public tunnel can lag behind provider-state
      // verification, so an early hypothesis may temporarily be
      // WEBHOOK_NOT_RECEIVED or PENDING_ASYNC_PROCESSING.
      updateDemoStep(
        "diagnose",
        "RUNNING",
        "Waiting for webhook failure evidence and deterministic root-cause confirmation…"
      );

      const diagnosis =
        await waitForExpectedDiagnosis(orderId);

      const report = diagnosis.report;
      const primary =
        report?.investigation
          ?.primary_hypothesis;

      if (!diagnosis.confirmed) {
        const observed =
          primary?.code || "NO_ROOT_CAUSE";

        throw new Error(
          observed === "WEBHOOK_NOT_RECEIVED"
            ? "Webhook failure evidence did not arrive. Check that the zrok tunnel is running and the Razorpay Test Mode webhook URL points to the current tunnel."
            : `Expected WEBHOOK_HANDLER_FAILURE, but PayTrace still reports ${observed}.`
        );
      }

      updateDemoStep(
        "diagnose",
        "PASS",
        `${primary.code} · ${Math.round(
          (primary.confidence || 0) * 100
        )}% confidence`
      );

      // 5. Reproduce.
      updateDemoStep("reproduce", "RUNNING");

      const reproductionResponse = await fetch(
        `${API_URL}/api/orders/${orderId}/reproduce`,
        {
          method: "POST",
        }
      );

      const reproduction =
        await reproductionResponse.json();

      if (
        !reproductionResponse.ok ||
        reproduction?.reproduction?.result !==
          "REPRODUCED" ||
        reproduction?.reproduction
          ?.hypothesis_status !== "CONFIRMED"
      ) {
        throw new Error(
          "PayTrace could not reproduce and confirm the incident."
        );
      }

      updateDemoStep(
        "reproduce",
        "PASS",
        "Failure signature reproduced; hypothesis confirmed."
      );

      // 6. Verify the test-lab fix.
      updateDemoStep("verify", "RUNNING");

      const verifyFixResponse = await fetch(
        `${API_URL}/api/orders/${orderId}/verify-fix`,
        {
          method: "POST",
        }
      );

      const verifiedFix =
        await verifyFixResponse.json();

      if (
        !verifyFixResponse.ok ||
        verifiedFix?.final_verdict !==
          "FIX_VERIFIED"
      ) {
        throw new Error(
          "Regression verification did not produce FIX_VERIFIED."
        );
      }

      updateDemoStep(
        "verify",
        "PASS",
        "Regression passed · FIX_VERIFIED"
      );

      setDemoVerdict("FIX_VERIFIED");

      // We are done injecting failure. Leave the environment safe.
      await fetch(
        `${API_URL}/api/faults/webhook/disable`,
        {
          method: "POST",
        }
      );

      faultWasEnabled = false;
      setFaultEnabled(false);

      await loadDashboard();
      setSelectedOrderId(orderId);
      await loadReport(orderId);
    } catch (error) {
      console.error(error);
      setDemoError(error.message);

      setDemoSteps((current) => {
        let failedAssigned = false;

        return current.map((step) => {
          if (
            !failedAssigned &&
            step.status === "RUNNING"
          ) {
            failedAssigned = true;

            return {
              ...step,
              status: "FAIL",
              result: error.message,
            };
          }

          return step;
        });
      });
    } finally {
      if (faultWasEnabled) {
        try {
          await fetch(
            `${API_URL}/api/faults/webhook/disable`,
            {
              method: "POST",
            }
          );
          setFaultEnabled(false);
        } catch (error) {
          console.error(
            "Failed to disable demo fault:",
            error
          );
        }
      }

      setDemoRunning(false);
    }
  }

  async function runReliabilitySuite() {
    setSuiteRunning(true);

    try {
      const response = await fetch(
        `${API_URL}/api/reliability/suite/run`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Reliability suite execution failed"
        );
      }

      setReliabilitySuite(data);
      await loadDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setSuiteRunning(false);
    }
  }

  async function toggleFault(enable) {
    const endpoint = enable
      ? "/api/faults/webhook/enable"
      : "/api/faults/webhook/disable";

    await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
    });

    setFaultEnabled(enable);
  }

  async function exportIncidentReport(orderId) {
    if (!orderId || exportingReport) return;

    setExportingReport(true);

    try {
      const response = await fetch(
        `${API_URL}/api/orders/${orderId}/export/pdf`
      );

      if (!response.ok) {
        const errorData = await response.json().catch(
          () => ({})
        );

        throw new Error(
          errorData.detail ||
            "Incident report export failed."
        );
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");

      anchor.href = url;
      anchor.download =
        `PayTrace_Incident_${orderId}.pdf`;

      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      setActionStatus(error.message);
    } finally {
      setExportingReport(false);
    }
  }

  async function runIncidentAction(action) {
    if (!selectedOrderId) return;

    const endpoint =
      action === "reproduce"
        ? `/api/orders/${selectedOrderId}/reproduce`
        : `/api/orders/${selectedOrderId}/verify-fix`;

    setActionStatus(
      action === "reproduce"
        ? "Reproducing failure signature…"
        : "Running regression verification…"
    );

    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Action failed");
      }

      setActionStatus(
        action === "reproduce"
          ? `Reproduction: ${data?.reproduction?.result || data?.status || "completed"}`
          : `Fix verification: ${data?.final_verdict || data?.status || "completed"}`
      );

      await loadReport(selectedOrderId);
      await loadDashboard();
    } catch (error) {
      console.error(error);
      setActionStatus(error.message);
    }
  }

  async function startPayment() {
    try {
      setPaymentStatus("Creating Razorpay test order…");

      const orderResponse = await fetch(
        `${API_URL}/api/orders`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            amount: 49900,
          }),
        }
      );

      const orderData = await orderResponse.json();

      if (!orderResponse.ok) {
        throw new Error(
          orderData.detail || "Order creation failed"
        );
      }

      const options = {
        key: orderData.key_id,
        amount: orderData.order.amount,
        currency: orderData.order.currency,
        name: "PayTrace AI",
        description: "Payment reliability test",
        order_id: orderData.order.id,

        handler: async function (response) {
          setPaymentStatus(
            "Checkout completed. Verifying evidence…"
          );

          const verifyResponse = await fetch(
            `${API_URL}/api/payments/verify`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                razorpay_payment_id:
                  response.razorpay_payment_id,
                razorpay_order_id:
                  response.razorpay_order_id,
                razorpay_signature:
                  response.razorpay_signature,
              }),
            }
          );

          const verification =
            await verifyResponse.json();

          if (!verifyResponse.ok) {
            throw new Error(
              verification.detail ||
                "Payment verification failed"
            );
          }

          setLastPaymentOrder(
            response.razorpay_order_id
          );

          setPaymentStatus(
            faultEnabled
              ? "Fault injected. Waiting for PayTrace incident evidence…"
              : "Payment verified. Waiting for webhook convergence…"
          );

          setTimeout(async () => {
            await loadDashboard();
            setSelectedOrderId(
              response.razorpay_order_id
            );
            setView("incidents");
            setPaymentStatus("");
          }, 2200);
        },

        prefill: {
          name: "PayTrace Test User",
          email: "test@paytrace.dev",
          contact: "9999999999",
        },

        notes: {
          project: "PayTrace AI",
        },

        theme: {
          color: "#635bff",
        },
      };

      const checkout = new window.Razorpay(options);

      checkout.on("payment.failed", (response) => {
        setPaymentStatus(
          response?.error?.description ||
            "Test payment failed."
        );
      });

      checkout.open();
    } catch (error) {
      console.error(error);
      setPaymentStatus(error.message);
    }
  }

  const selectedOrderSummary = useMemo(
    () =>
      recentOrders.find(
        (order) => order.order_id === selectedOrderId
      ),
    [recentOrders, selectedOrderId]
  );

  const summary = dashboard?.summary || {};

  function navigateTo(nextView) {
    if (nextView === view) return;
    setView(nextView);
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">P</div>
          <div>
            <div className="brand-name">PayTrace</div>
            <div className="brand-subtitle">
              Payment Reliability
            </div>
          </div>
        </div>

        <nav className="nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${
                view === item.id ? "active" : ""
              }`}
              onClick={() => navigateTo(item.id)}
            >
              <span className="nav-dot" />
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-spacer" />

        <div className="environment-card">
          <div className="environment-label">
            Environment
          </div>
          <div className="environment-value">
            <span className="live-dot" />
            Razorpay Test Mode
          </div>
          <div className="environment-meta">
            Backend · localhost:8000
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">
              PAYMENT RELIABILITY ENGINEER
            </div>
            <h1>
              {view === "overview" && "Overview"}
              {view === "incidents" &&
                "Incident Workspace"}
              {view === "complaints" &&
                "Complaint Intake"}
              {view === "lab" &&
                "Reliability Lab"}
              {view === "audit" && "Audit Trail"}
            </h1>
          </div>

          <div className="topbar-actions">
            <button
              className="ghost-button"
              onClick={loadDashboard}
            >
              Refresh
            </button>

            <div className="status-chip">
              <span className="live-dot" />
              System online
            </div>
          </div>
        </header>

        <div
          className="razorpay-motion-strip"
          aria-hidden="true"
        >
          <div className="razorpay-motion-track">
            <div className="razorpay-motion-group">
              <span className="razorpay-word">
                RAZORPAY
              </span>
              <span className="motion-separator">/</span>
              <span>TEST MODE</span>
              <span className="motion-dot">●</span>
              <span>PAYTRACE AI</span>
              <span className="motion-dot">●</span>
              <span>PAYMENT RELIABILITY</span>
              <span className="motion-dot">●</span>
            </div>

            <div className="razorpay-motion-group">
              <span className="razorpay-word">
                RAZORPAY
              </span>
              <span className="motion-separator">/</span>
              <span>TEST MODE</span>
              <span className="motion-dot">●</span>
              <span>PAYTRACE AI</span>
              <span className="motion-dot">●</span>
              <span>PAYMENT RELIABILITY</span>
              <span className="motion-dot">●</span>
            </div>
          </div>
        </div>

        <div className="view-stage" key={view}>
        {view === "overview" && (
          <Overview
            loading={loading}
            dashboard={dashboard}
            onOpenOrder={(orderId) => {
              setSelectedOrderId(orderId);
              navigateTo("incidents");
            }}
          />
        )}

        {view === "incidents" && (
          <IncidentWorkspace
            orders={recentOrders}
            selectedOrderId={selectedOrderId}
            setSelectedOrderId={setSelectedOrderId}
            selectedOrderSummary={selectedOrderSummary}
            report={report}
            reportLoading={reportLoading}
            reload={() =>
              selectedOrderId &&
              loadReport(selectedOrderId)
            }
            runIncidentAction={runIncidentAction}
            actionStatus={actionStatus}
            exportIncidentReport={exportIncidentReport}
            exportingReport={exportingReport}
          />
        )}

        {view === "complaints" && (
          <ComplaintIntake
            complaints={complaints}
            result={complaintResult}
            submitting={complaintSubmitting}
            selectedOrderId={selectedOrderId}
            submitComplaint={submitComplaint}
            onOpenOrder={(orderId) => {
              setSelectedOrderId(orderId);
              navigateTo("incidents");
            }}
          />
        )}

        {view === "lab" && (
          <ReliabilityLab
            faultEnabled={faultEnabled}
            toggleFault={toggleFault}
            startPayment={startPayment}
            paymentStatus={paymentStatus}
            lastPaymentOrder={lastPaymentOrder}
            reliabilitySuite={reliabilitySuite}
            suiteRunning={suiteRunning}
            runReliabilitySuite={runReliabilitySuite}
            demoRunning={demoRunning}
            demoSteps={demoSteps}
            demoOrderId={demoOrderId}
            demoVerdict={demoVerdict}
            demoError={demoError}
            runPayTraceDemo={runPayTraceDemo}
            onOpenDemoOrder={() => {
              if (demoOrderId) {
                setSelectedOrderId(demoOrderId);
                navigateTo("incidents");
              }
            }}
          />
        )}

        {view === "audit" && (
          <AuditTrail
            report={report}
            orders={recentOrders}
            selectedOrderId={selectedOrderId}
            setSelectedOrderId={setSelectedOrderId}
          />
        )}
        </div>
      </main>
    </div>
  );
}

function Overview({
  loading,
  dashboard,
  onOpenOrder,
}) {
  if (loading && !dashboard) {
    return <LoadingState label="Loading PayTrace…" />;
  }

  const summary = dashboard?.summary || {};
  const recent = dashboard?.recent_orders || [];

  return (
    <div className="page-grid">
      <section className="hero-card animated-hero">
        <div
          className="hero-brand-drift"
          aria-hidden="true"
        >
          <span>RAZORPAY</span>
          <span>PAYTRACE</span>
          <span>RAZORPAY</span>
          <span>PAYTRACE</span>
        </div>

        <div className="hero-content-layer">
          <div className="hero-label">
            CURRENT PAYMENT CONVERGENCE
          </div>
          <div className="hero-score">
            <AnimatedNumber
              value={
                dashboard?.current_convergence_rate ??
                dashboard?.current_health_rate ??
                100
              }
            />
            <span>%</span>
          </div>
        </div>


        <div className="hero-copy hero-content-layer">
          <h2>Payment systems fail between states.</h2>
          <p>
            Across completed test payments, PayTrace compares
            provider truth with merchant state, reconstructs
            failures and verifies whether fixes remove the same
            divergence.
          </p>
          <div className="hero-footnote">
            {dashboard?.evaluated_orders ?? 0} evaluated orders · pending records excluded
          </div>
        </div>
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Reliability score"
          value={
            dashboard?.reliability_score != null
              ? `${dashboard.reliability_score}`
              : "—"
          }
          detail={
            dashboard?.reliability_total
              ? `${dashboard.reliability_passed}/${dashboard.reliability_total} executable scenarios passed`
              : "Run the reliability suite"
          }
          tone="score"
        />
        <MetricCard
          label="Transactions"
          value={summary.total_orders ?? 0}
          detail="Tracked test orders"
        />
        <MetricCard
          label="Active incidents"
          value={summary.active_incidents ?? 0}
          detail={
            (summary.active_incidents ?? 0) > 0
              ? "Requires investigation"
              : "No active divergence"
          }
          tone={
            (summary.active_incidents ?? 0) > 0
              ? "danger-live"
              : "healthy-zero"
          }
        />
        <MetricCard
          label="Recovered"
          value={summary.recovered ?? 0}
          detail="Historical failures resolved"
          tone="success"
        />
        <MetricCard
          label="Fixes verified"
          value={summary.verified_fixes ?? 0}
          detail="Regression tests passed"
          tone="success"
        />
      </section>

      <section className="panel full-span">
        <div className="panel-header">
          <div>
            <div className="section-kicker">
              RECENT ACTIVITY
            </div>
            <h2>Orders & incidents</h2>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Status</th>
                <th>Merchant state</th>
                <th>Root cause</th>
                <th>Fix</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {recent.map((order, index) => (
                <tr
                  key={order.order_id}
                  className="recent-activity-row"
                  style={{
                    "--row-delay": `${index * 50}ms`,
                  }}
                >
                  <td>
                    <div className="mono strong">
                      {shorten(order.order_id, 22)}
                    </div>
                    <div className="muted small">
                      {formatMoney(order.amount)}
                    </div>
                  </td>
                  <td>
                    <StatusBadge
                      status={order.status}
                    />
                  </td>
                  <td className="mono">
                    {order.merchant_state}
                  </td>
                  <td>
                    {order.incident_type || "—"}
                  </td>
                  <td>
                    {order.fix_verification === "PASS"
                      ? "Verified"
                      : "—"}
                  </td>
                  <td>
                    <button
                      className="text-button"
                      onClick={() =>
                        onOpenOrder(order.order_id)
                      }
                    >
                      Open →
                    </button>
                  </td>
                </tr>
              ))}

              {!recent.length && (
                <tr>
                  <td
                    colSpan="6"
                    className="empty-cell"
                  >
                    No PayTrace orders yet. Run a test
                    payment from Reliability Lab.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  tone = "neutral",
}) {
  return (
    <div className={`metric-card ${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        <AnimatedNumber value={value} />
      </div>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}

function IncidentWorkspace({
  orders,
  selectedOrderId,
  setSelectedOrderId,
  selectedOrderSummary,
  report,
  reportLoading,
  reload,
  runIncidentAction,
  actionStatus,
  exportIncidentReport,
  exportingReport,
}) {
  const analysis = report?.analysis || {};
  const investigation =
    report?.investigation || {};
  const primary =
    investigation?.primary_hypothesis || {};
  const timeline = report?.timeline?.timeline || [];
  const fix = report?.fix?.fix;
  const reproduction =
    report?.latest_reproduction;
  const regression =
    report?.latest_regression;

  const incidentPhase =
    incidentPhaseCopy(investigation.status);

  const confidencePercent =
    primary.confidence != null
      ? Math.round(primary.confidence * 100)
      : null;

  const reproductionVerified =
    reproduction?.status === "REPRODUCED" &&
    reproduction?.metadata?.hypothesis_status ===
      "CONFIRMED";

  const regressionVerified =
    regression?.status === "PASS" &&
    regression?.metadata?.fix_status ===
      "VERIFIED";

  return (
    <div className="incident-layout">
      <section className="incident-list panel">
        <div className="panel-header">
          <div>
            <div className="section-kicker">
              ORDERS
            </div>
            <h2>Investigations</h2>
          </div>
        </div>

        <div className="order-list">
          {orders.map((order) => (
            <button
              key={order.order_id}
              className={`order-item ${
                selectedOrderId === order.order_id
                  ? "selected"
                  : ""
              }`}
              onClick={() =>
                setSelectedOrderId(order.order_id)
              }
            >
              <div className="order-item-top">
                <span className="mono">
                  {shorten(order.order_id, 18)}
                </span>
                <StatusBadge
                  status={order.status}
                  compact
                />
              </div>

              <div className="order-item-bottom">
                <span>{formatMoney(order.amount)}</span>
                <span>{order.merchant_state}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="workspace">
        {reportLoading ? (
          <LoadingState label="Reconstructing evidence…" />
        ) : !report ? (
          <EmptyState />
        ) : (
          <>
            <div className="incident-header panel">
              <div className="incident-title-block">
                <div className="section-kicker">
                  INCIDENT REPORT
                </div>
                <h2>
                  {primary.title ||
                    (investigation.status === "HEALTHY"
                      ? "Payment state consistent"
                      : "Payment reliability analysis")}
                </h2>

                <div className="incident-meta">
                  <span className="mono">
                    {report.order.id}
                  </span>
                  <span>·</span>
                  <span>
                    {formatMoney(
                      report.order.amount
                    )}
                  </span>
                  <span>·</span>
                  <span>
                    {formatTime(
                      report.order.updated_at
                    )}
                  </span>
                </div>
              </div>

              <div className="incident-header-actions">
                <StatusBadge
                  status={investigation.status}
                />

                <button
                  className="report-export-button prominent"
                  onClick={() =>
                    exportIncidentReport(
                      report.order.id
                    )
                  }
                  disabled={exportingReport}
                >
                  <span className="export-icon">⇩</span>
                  {exportingReport
                    ? "Preparing PDF…"
                    : "Export Incident PDF"}
                </button>

                <button
                  className="ghost-button"
                  onClick={reload}
                >
                  Refresh
                </button>
              </div>
            </div>

            <div
              className={`incident-phase-banner ${incidentPhase.tone}`}
            >
              <div className="incident-phase-icon">
                {investigation.status === "RECOVERED"
                  ? "✓"
                  : investigation.status === "INVESTIGATED"
                  ? "!"
                  : investigation.status === "HEALTHY"
                  ? "✓"
                  : "…"}
              </div>

              <div>
                <strong>{incidentPhase.title}</strong>
                <span>{incidentPhase.detail}</span>
              </div>

              {investigation.status === "RECOVERED" && (
                <div className="history-retained">
                  HISTORICAL EVIDENCE RETAINED
                </div>
              )}
            </div>

            <div
              className={`state-comparison ${
                analysis?.state_divergence
                  ? "diverged"
                  : "converged"
              }`}
            >
              <StateCard
                label="Provider truth"
                value={
                  analysis?.provider_state
                    ?.payment_captured
                    ? "CAPTURED"
                    : "UNKNOWN"
                }
                good={
                  analysis?.provider_state
                    ?.payment_captured
                }
              />

              <div className="state-bridge">
                <div className="state-bridge-line" />
                <div
                  className={`state-arrow ${
                    analysis?.state_divergence
                      ? "diverged"
                      : "converged"
                  }`}
                >
                  {analysis?.state_divergence
                    ? "≠"
                    : "="}
                </div>
                <div className="state-bridge-copy">
                  {analysis?.state_divergence
                    ? "STATE DIVERGENCE"
                    : "STATE CONVERGED"}
                </div>
              </div>

              <StateCard
                label="Merchant truth"
                value={report.order.merchant_state}
                good={
                  report.order.merchant_state ===
                  "PAID"
                }
              />
            </div>

            <div className="workspace-columns">
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <div className="section-kicker">
                      ROOT CAUSE
                    </div>
                    <h2>
                      {primary.code ||
                        "No active root cause"}
                    </h2>
                  </div>

                  {confidencePercent != null && (
                    <div
                      className="confidence-ring"
                      style={{
                        "--confidence": `${confidencePercent * 3.6}deg`,
                      }}
                    >
                      <div className="confidence-ring-inner">
                        <strong>
                          {confidencePercent}%
                        </strong>
                        <span>CONFIDENCE</span>
                      </div>
                    </div>
                  )}
                </div>

                <p className="body-copy">
                  {primary.reason ||
                    "Provider and merchant state are currently consistent."}
                </p>

                {primary.failure_boundary && (
                  <div className="failure-boundary-card">
                    <div>
                      <span>FAILURE BOUNDARY</span>
                      <strong>
                        {primary.failure_boundary}
                      </strong>
                    </div>

                    <div className="boundary-flow">
                      <span>Provider</span>
                      <i>→</i>
                      <b>Webhook handler</b>
                      <i>→</i>
                      <span>Merchant</span>
                    </div>
                  </div>
                )}

                <div className="evidence-list">
                  {(primary.supporting_evidence ||
                    analysis.evidence ||
                    []).map((item, index) => (
                    <div
                      className="evidence-item"
                      key={index}
                    >
                      <span className="check">✓</span>
                      <span>
                        {typeof item === "string"
                          ? item
                          : item.statement}
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div>
                    <div className="section-kicker">
                      VERIFICATION
                    </div>
                    <h2>Resolution proof</h2>
                  </div>
                </div>

                <div className="proof-chain">
                  <VerificationRow
                    step="01"
                    label="Failure reproduced"
                    value={
                      reproduction?.status ===
                      "REPRODUCED"
                    }
                  />

                  <VerificationRow
                    step="02"
                    label="Hypothesis confirmed"
                    value={
                      reproduction?.metadata
                        ?.hypothesis_status ===
                      "CONFIRMED"
                    }
                  />

                  <VerificationRow
                    step="03"
                    label="Regression passed"
                    value={
                      regression?.status === "PASS"
                    }
                  />

                  <VerificationRow
                    step="04"
                    label="Fix verified"
                    value={
                      regression?.metadata
                        ?.fix_status === "VERIFIED"
                    }
                  />
                </div>

                <div
                  className={`proof-verdict ${
                    regressionVerified
                      ? "verified"
                      : reproductionVerified
                      ? "confirmed"
                      : "pending"
                  }`}
                >
                  <span>
                    {regressionVerified
                      ? "FINAL VERDICT"
                      : reproductionVerified
                      ? "HYPOTHESIS"
                      : "VERIFICATION"}
                  </span>
                  <strong>
                    {regressionVerified
                      ? "FIX_VERIFIED"
                      : reproductionVerified
                      ? "CONFIRMED"
                      : "IN PROGRESS"}
                  </strong>
                </div>

                <div className="verification-actions">
                  <button
                    className="ghost-button"
                    onClick={() => runIncidentAction("reproduce")}
                    disabled={!primary.code}
                  >
                    Reproduce failure
                  </button>
                  <button
                    className="primary-button"
                    onClick={() => runIncidentAction("verify-fix")}
                    disabled={!primary.code}
                  >
                    Verify fix
                  </button>
                </div>

                {actionStatus && (
                  <div className="action-status">
                    {actionStatus}
                  </div>
                )}
              </section>
            </div>

            <section className="panel">
              <div className="panel-header">
                <div>
                  <div className="section-kicker">
                    EVENT TIMELINE
                  </div>
                  <h2>What happened</h2>
                </div>

                <span className="muted">
                  {timeline.length} events
                </span>
              </div>

              <div className="timeline">
                {timeline.map((event, index) => (
                  <div
                    className="timeline-item timeline-animated"
                    key={`${event.sequence}-${event.type}`}
                    style={{
                      "--timeline-delay": `${Math.min(index, 14) * 45}ms`,
                    }}
                  >
                    <div
                      className={`timeline-node ${
                        event.status === "FAILED"
                          ? "failed"
                          : event.status === "PASS" ||
                            event.status ===
                              "REPRODUCED"
                          ? "passed"
                          : ""
                      }`}
                    />

                    <div className="timeline-content">
                      <div className="timeline-top">
                        <strong>{event.type}</strong>
                        <span>
                          {formatTime(event.timestamp)}
                        </span>
                      </div>

                      <div className="timeline-message">
                        {event.message}
                      </div>

                      <div className="timeline-source">
                        {event.source} ·{" "}
                        {event.status || "event"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {fix && (
              <section
                className={`panel fix-panel ${
                  regressionVerified
                    ? "fix-verified"
                    : ""
                }`}
              >
                <div className="panel-header">
                  <div>
                    <div className="section-kicker">
                      {regressionVerified
                        ? "VERIFIED FIX DIRECTION"
                        : "PROPOSED FIX DIRECTION"}
                    </div>
                    <h2>{fix.title}</h2>
                  </div>
                </div>

                <p className="body-copy">
                  {fix.summary}
                </p>

                <div className="fix-grid">
                  {fix.changes?.map((change) => (
                    <div
                      className="fix-item"
                      key={change.priority}
                    >
                      <div className="fix-number">
                        {change.priority}
                      </div>
                      <div>
                        <strong>
                          {change.change}
                        </strong>
                        <p>{change.why}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function ComplaintIntake({
  complaints,
  result,
  submitting,
  selectedOrderId,
  submitComplaint,
  onOpenOrder,
}) {
  const [message, setMessage] = useState(
    "Customer says ₹499 was deducted but the merchant dashboard still shows the payment as pending."
  );
  const [orderId, setOrderId] = useState(
    selectedOrderId || ""
  );
  const [paymentId, setPaymentId] = useState("");

  useEffect(() => {
    if (selectedOrderId && !orderId) {
      setOrderId(selectedOrderId);
    }
  }, [selectedOrderId]);

  const correlation = result?.correlation || {};
  const matched = correlation?.matched_order;
  const truth = correlation?.system_truth || {};

  async function handleSubmit(event) {
    event.preventDefault();

    try {
      await submitComplaint({
        message,
        order_id: orderId.trim() || null,
        payment_id: paymentId.trim() || null,
      });
    } catch (error) {
      console.error(error);
    }
  }

  return (
    <div className="complaint-grid">
      <section className="panel complaint-form-panel">
        <div className="section-kicker">
          NATURAL-LANGUAGE ISSUE INTAKE
        </div>
        <h2>What did the customer or merchant report?</h2>
        <p className="body-copy">
          PayTrace treats the complaint as a claim, then
          correlates it with deterministic payment evidence
          before concluding what actually happened.
        </p>

        <form onSubmit={handleSubmit}>
          <label className="field-label">
            Complaint
          </label>
          <textarea
            className="complaint-textarea"
            value={message}
            onChange={(event) =>
              setMessage(event.target.value)
            }
            placeholder="Example: Money was deducted, but the merchant still shows payment pending."
          />

          <div className="complaint-fields">
            <div>
              <label className="field-label">
                Order ID
              </label>
              <input
                value={orderId}
                onChange={(event) =>
                  setOrderId(event.target.value)
                }
                placeholder="order_..."
              />
            </div>

            <div>
              <label className="field-label">
                Payment ID
              </label>
              <input
                value={paymentId}
                onChange={(event) =>
                  setPaymentId(event.target.value)
                }
                placeholder="pay_..."
              />
            </div>
          </div>

          <div className="complaint-form-actions">
            <button
              className="primary-button"
              type="submit"
              disabled={submitting}
            >
              {submitting
                ? "Correlating evidence…"
                : "Investigate complaint"}
            </button>

            <button
              className="ghost-button"
              type="button"
              onClick={() =>
                setMessage(
                  "Customer says ₹499 was deducted but the merchant dashboard still shows the payment as pending."
                )
              }
            >
              Use demo complaint
            </button>
          </div>
        </form>
      </section>

      <section className="panel complaint-result-panel">
        <div className="section-kicker">
          EVIDENCE CORRELATION
        </div>
        <h2>
          {result
            ? statusLabel(
                correlation?.status
              )
            : "Waiting for a complaint"}
        </h2>

        {!result ? (
          <div className="complaint-placeholder">
            Submit a complaint to compare the reported
            symptom with PayTrace's recorded provider,
            webhook and merchant-state evidence.
          </div>
        ) : (
          <>
            <div className="correlation-header">
              <div>
                <span className="muted small">
                  Reported issue
                </span>
                <strong>
                  {result.reported_issue_type}
                </strong>
              </div>
              <div className="correlation-confidence">
                <strong>
                  {Math.round(
                    (correlation.confidence_score || 0) *
                      100
                  )}
                  %
                </strong>
                <span>
                  {correlation.confidence} match
                </span>
              </div>
            </div>

            <div className="detail-row">
              <span>Correlation basis</span>
              <code>{correlation.basis}</code>
            </div>

            <div className="detail-row">
              <span>Evidence status</span>
              <code>
                {correlation.evidence_status || "UNVERIFIED"}
              </code>
            </div>

            {matched && (
              <div className="matched-order-card">
                <div>
                  <span className="muted small">
                    Matched order
                  </span>
                  <strong className="mono">
                    {matched.order_id}
                  </strong>
                </div>

                <div>
                  <span className="muted small">
                    Merchant state
                  </span>
                  <strong>
                    {truth.merchant_state || "—"}
                  </strong>
                </div>

                <div>
                  <span className="muted small">
                    Root cause
                  </span>
                  <strong>
                    {truth.root_cause || "No active root cause"}
                  </strong>
                </div>
              </div>
            )}

            {truth && matched && (
              <div className="complaint-truth">
                <div className="section-kicker">
                  SYSTEM TRUTH
                </div>
                <div className="truth-grid">
                  <div>
                    <span>Provider paid</span>
                    <strong>
                      {truth.provider_state
                        ?.payment_captured ||
                      truth.provider_state
                        ?.order_paid
                        ? "YES"
                        : "NO / UNKNOWN"}
                    </strong>
                  </div>
                  <div>
                    <span>Merchant state</span>
                    <strong>
                      {truth.merchant_state || "—"}
                    </strong>
                  </div>
                  <div>
                    <span>State divergence</span>
                    <strong
                      className={
                        truth.state_divergence
                          ? "danger-text"
                          : "success-text"
                      }
                    >
                      {truth.state_divergence
                        ? "DETECTED"
                        : "NOT ACTIVE"}
                    </strong>
                  </div>
                </div>
              </div>
            )}

            {matched && (
              <button
                className="primary-button complaint-open-button"
                onClick={() =>
                  onOpenOrder(matched.order_id)
                }
              >
                Open Incident Workspace →
              </button>
            )}

            {!matched &&
              correlation.candidates?.length > 0 && (
                <div className="candidate-list">
                  <div className="section-kicker">
                    POSSIBLE MATCHES
                  </div>

                  {correlation.candidates.map(
                    (candidate) => (
                      <button
                        className="candidate-row"
                        key={candidate.order_id}
                        onClick={() =>
                          onOpenOrder(
                            candidate.order_id
                          )
                        }
                      >
                        <span className="mono">
                          {shorten(
                            candidate.order_id,
                            24
                          )}
                        </span>
                        <span>
                          {candidate.investigation_status}
                        </span>
                      </button>
                    )
                  )}
                </div>
              )}
          </>
        )}
      </section>

      <section className="panel full-span">
        <div className="panel-header">
          <div>
            <div className="section-kicker">
              RECENT COMPLAINTS
            </div>
            <h2>Complaint correlation history</h2>
          </div>
        </div>

        <div className="complaint-history">
          {complaints.map((complaint) => {
            const itemCorrelation =
              complaint.correlation || {};
            const itemMatched =
              itemCorrelation.matched_order;

            return (
              <div
                className="complaint-history-row"
                key={complaint.complaint_id}
              >
                <div>
                  <strong>
                    {complaint.reported_issue_type}
                  </strong>
                  <p>{complaint.message}</p>
                </div>

                <div>
                  <span className="muted small">
                    Correlation
                  </span>
                  <strong>
                    {itemCorrelation.status}
                  </strong>
                </div>

                <div>
                  <span className="muted small">
                    Order
                  </span>
                  <strong className="mono">
                    {itemMatched?.order_id
                      ? shorten(
                          itemMatched.order_id,
                          22
                        )
                      : "Unresolved"}
                  </strong>
                </div>

                <div>
                  {itemMatched ? (
                    <button
                      className="text-button"
                      onClick={() =>
                        onOpenOrder(
                          itemMatched.order_id
                        )
                      }
                    >
                      Open →
                    </button>
                  ) : (
                    <span className="muted small">
                      Needs identifier
                    </span>
                  )}
                </div>
              </div>
            );
          })}

          {!complaints.length && (
            <div className="empty-cell">
              No complaints have been submitted yet.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}


function ReliabilityLab({
  faultEnabled,
  toggleFault,
  startPayment,
  paymentStatus,
  lastPaymentOrder,
  reliabilitySuite,
  suiteRunning,
  runReliabilitySuite,
  demoRunning,
  demoSteps,
  demoOrderId,
  demoVerdict,
  demoError,
  runPayTraceDemo,
  onOpenDemoOrder,
}) {
  return (
    <div className="lab-grid">
      <section className="panel full-span demo-orchestrator">
        <div className="demo-orchestrator-head">
          <div>
            <div className="section-kicker">
              BUILDATHON DEMO MODE
            </div>
            <h2>Run one guided PayTrace incident</h2>
            <p className="body-copy">
              One button prepares the fault, opens Razorpay Test Mode,
              detects the resulting divergence, diagnoses it, reproduces
              the failure and verifies the fix. Checkout confirmation
              remains intentionally human-controlled.
            </p>
          </div>

          <button
            className="demo-launch-button"
            onClick={runPayTraceDemo}
            disabled={demoRunning}
          >
            {demoRunning
              ? "Demo running…"
              : "▶ Run PayTrace Demo"}
          </button>
        </div>

        <div className="demo-progress-grid">
          {demoSteps.map((step, index) => (
            <div
              className={`demo-progress-step ${step.status.toLowerCase()}`}
              key={step.id}
            >
              <div className="demo-progress-top">
                <span className="demo-step-number">
                  {index + 1}
                </span>
                <span className="demo-step-status">
                  {step.status}
                </span>
              </div>

              <strong>{step.label}</strong>
              <p>{step.detail}</p>

              {step.result && (
                <div className="demo-step-result">
                  {step.result}
                </div>
              )}
            </div>
          ))}
        </div>

        {(demoVerdict || demoError) && (
          <div
            className={`demo-verdict ${
              demoVerdict ? "success" : "error"
            }`}
          >
            <div>
              <span>
                {demoVerdict
                  ? "DEMO COMPLETE"
                  : "DEMO INTERRUPTED"}
              </span>
              <strong>
                {demoVerdict ||
                  demoError}
              </strong>
              {demoOrderId && (
                <code>{demoOrderId}</code>
              )}
            </div>

            {demoOrderId && (
              <button
                className="ghost-button"
                onClick={onOpenDemoOrder}
              >
                Open Incident Workspace →
              </button>
            )}
          </div>
        )}
      </section>

      <section className="panel lab-hero">
        <div>
          <div className="section-kicker">
            CONTROLLED FAILURE INJECTION
          </div>
          <h2>Webhook processing failure</h2>
          <p className="body-copy">
            Reproduce the merchant-side failure boundary
            without touching production money or customer
            traffic.
          </p>
        </div>

        <div
          className={`fault-indicator ${
            faultEnabled ? "enabled" : ""
          }`}
        >
          <span />
          {faultEnabled
            ? "FAULT ENABLED"
            : "HEALTHY MODE"}
        </div>

        <div className="lab-actions">
          <button
            className="primary-button"
            onClick={startPayment}
          >
            Run ₹499 Test Payment
          </button>

          <button
            className={
              faultEnabled
                ? "danger-button"
                : "ghost-button"
            }
            onClick={() =>
              toggleFault(!faultEnabled)
            }
          >
            {faultEnabled
              ? "Disable fault"
              : "Enable webhook fault"}
          </button>
        </div>

        {paymentStatus && (
          <div className="lab-status">
            {paymentStatus}
          </div>
        )}

        {lastPaymentOrder && (
          <div className="detail-row">
            <span>Last test order</span>
            <code>{lastPaymentOrder}</code>
          </div>
        )}
      </section>

      <section className="panel reliability-suite-panel">
        <div className="panel-header">
          <div>
            <div className="section-kicker">
              EXECUTABLE RELIABILITY SUITE
            </div>
            <h2>Reliability score</h2>
          </div>

          <div className="suite-score">
            <strong>
              {reliabilitySuite?.score ?? "—"}
            </strong>
            <span>/100</span>
          </div>
        </div>

        <p className="body-copy">
          The score is earned from executable assertions,
          not manually assigned.
        </p>

        <button
          className="primary-button suite-run-button"
          onClick={runReliabilitySuite}
          disabled={suiteRunning}
        >
          {suiteRunning
            ? "Running 5 scenarios…"
            : "Run Full Reliability Suite"}
        </button>

        <div className="scenario-list">
          {(reliabilitySuite?.scenarios || [
            {
              scenario_id: "NORMAL_PAYMENT",
              title: "Normal payment convergence",
              result: "NOT_RUN",
            },
            {
              scenario_id: "WEBHOOK_HANDLER_RETRY",
              title: "Webhook handler failure + retry",
              result: "NOT_RUN",
            },
            {
              scenario_id: "DUPLICATE_WEBHOOK",
              title: "Duplicate webhook idempotency",
              result: "NOT_RUN",
            },
            {
              scenario_id: "OUT_OF_ORDER_EVENTS",
              title: "Out-of-order event tolerance",
              result: "NOT_RUN",
            },
            {
              scenario_id: "DELAYED_WEBHOOK_RECOVERY",
              title: "Delayed webhook recovery",
              result: "NOT_RUN",
            },
          ]).map((scenario) => (
            <ScenarioRow
              key={scenario.scenario_id}
              title={scenario.title}
              status={scenario.result}
            />
          ))}
        </div>

        {reliabilitySuite?.executed_at && (
          <div className="suite-meta">
            Last run · {formatTime(
              reliabilitySuite.executed_at
            )}
          </div>
        )}
      </section>

      <section className="panel full-span demo-flow-panel">
        <div className="section-kicker">
          JUDGE DEMO FLOW
        </div>
        <h2>Detect → Diagnose → Reproduce → Verify</h2>

        <div className="demo-flow">
          <div><strong>1</strong><span>Enable webhook fault</span></div>
          <div><strong>2</strong><span>Run test payment</span></div>
          <div><strong>3</strong><span>Open incident workspace</span></div>
          <div><strong>4</strong><span>Reproduce failure</span></div>
          <div><strong>5</strong><span>Verify fix</span></div>
        </div>
      </section>

      <section className="panel full-span">
        <div className="section-kicker">
          SAFETY BOUNDARY
        </div>
        <h2>What the lab will never do</h2>

        <div className="safety-grid">
          <SafetyItem text="No production code modifications" />
          <SafetyItem text="No real-money transactions" />
          <SafetyItem text="No customer contact" />
          <SafetyItem text="No automated refund or charge action" />
        </div>
      </section>
    </div>
  );
}

function AuditTrail({
  report,
  orders,
  selectedOrderId,
  setSelectedOrderId,
}) {
  const timeline = report?.timeline?.timeline || [];

  return (
    <div className="page-grid">
      <section className="panel full-span">
        <div className="panel-header">
          <div>
            <div className="section-kicker">
              ORDER AUDIT
            </div>
            <h2>Immutable evidence trail</h2>
          </div>

          <select
            value={selectedOrderId || ""}
            onChange={(event) =>
              setSelectedOrderId(event.target.value)
            }
          >
            {orders.map((order) => (
              <option
                value={order.order_id}
                key={order.order_id}
              >
                {order.order_id}
              </option>
            ))}
          </select>
        </div>

        <div className="audit-list">
          {timeline.map((event) => (
            <div
              className="audit-row"
              key={`${event.sequence}-${event.type}`}
            >
              <div className="audit-sequence">
                {String(event.sequence).padStart(
                  2,
                  "0"
                )}
              </div>
              <div>
                <strong>{event.type}</strong>
                <p>{event.message}</p>
              </div>
              <div className="audit-source">
                {event.source}
              </div>
              <div className="audit-time">
                {formatTime(event.timestamp)}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function StateCard({
  label,
  value,
  good,
}) {
  return (
    <div
      className={`state-card ${
        good ? "good" : "bad"
      }`}
    >
      <div className="state-label">{label}</div>
      <div className="state-value">{value}</div>
      <div className="state-status">
        {good ? "✓ Consistent" : "! Attention"}
      </div>
    </div>
  );
}

function VerificationRow({
  step,
  label,
  value,
}) {
  return (
    <div
      className={`verification-row ${
        value ? "verified" : "pending"
      }`}
    >
      <div className="verification-label">
        {step && (
          <span className="verification-step">
            {step}
          </span>
        )}
        <span>{label}</span>
      </div>

      <strong className={value ? "yes" : "no"}>
        {value ? "VERIFIED" : "PENDING"}
      </strong>
    </div>
  );
}

function StatusBadge({
  status,
  compact = false,
}) {
  return (
    <span
      className={`badge ${statusTone(
        status
      )} ${compact ? "compact" : ""}`}
    >
      {statusLabel(status)}
    </span>
  );
}

function ScenarioRow({
  title,
  status,
}) {
  return (
    <div className="scenario-row">
      <span>{title}</span>
      <span
        className={`scenario-status ${status.toLowerCase()}`}
      >
        {status}
      </span>
    </div>
  );
}

function SafetyItem({ text }) {
  return (
    <div className="safety-item">
      <span>✓</span>
      {text}
    </div>
  );
}

function LoadingState({ label }) {
  return (
    <div className="loading-state">
      <div className="loading-ring" />
      <span>{label}</span>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="panel empty-state">
      Select an order to inspect its PayTrace report.
    </div>
  );
}

export default App;
