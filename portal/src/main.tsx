import "@/styles.css";

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { Outlet, RouterProvider, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { Shell } from "@/components/Shell";
import { call, type Me } from "@/lib/api";
import { MeContext } from "@/lib/session";
import { Approvals } from "@/pages/Approvals";
import { MyAssets } from "@/pages/Assets";
import { Home } from "@/pages/Home";
import { Inventory } from "@/pages/Inventory";
import { Leave } from "@/pages/Leave";
import { RequestDetail, RequestNew, RequestsList } from "@/pages/Requests";

function Root() {
  // A failed `me` call means there is no session: use Frappe's sign-in page, then come back here.
  const me = useQuery({ queryKey: ["me"], queryFn: () => call<Me>("staffdock.api.me"), retry: false });
  if (me.isError) {
    window.location.assign(`/login?${new URLSearchParams({ "redirect-to": window.location.pathname })}`);
    return null;
  }
  if (!me.data) return null;
  return (
    <MeContext.Provider value={me.data}>
      <Shell>
        <Outlet />
      </Shell>
    </MeContext.Provider>
  );
}

const root = createRootRoute({ component: Root });
const routeTree = root.addChildren([
  createRoute({ getParentRoute: () => root, path: "/", component: Home }),
  createRoute({ getParentRoute: () => root, path: "/requests", component: RequestsList }),
  createRoute({ getParentRoute: () => root, path: "/requests/new", component: RequestNew }),
  createRoute({ getParentRoute: () => root, path: "/requests/$name", component: RequestDetail }),
  createRoute({ getParentRoute: () => root, path: "/leave", component: Leave }),
  createRoute({ getParentRoute: () => root, path: "/approvals", component: Approvals }),
  createRoute({ getParentRoute: () => root, path: "/assets", component: MyAssets }),
  createRoute({ getParentRoute: () => root, path: "/inventory", component: Inventory }),
]);

const router = createRouter({ routeTree, basepath: "/staff" });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
