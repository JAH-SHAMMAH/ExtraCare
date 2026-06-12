"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { transportApi } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────────────────

export type VehicleStatus = "active" | "maintenance" | "retired";
export type TripDirection = "morning" | "afternoon";
export type TripStatus = "planned" | "in_progress" | "completed" | "cancelled";
export type BoardingStatus = "expected" | "boarded" | "dropped_off" | "absent" | "skipped";

export interface VehicleRow {
  id: string;
  registration_number: string;
  make: string | null;
  model: string | null;
  color: string | null;
  capacity: number;
  fuel_type: string | null;
  status: VehicleStatus;
  last_serviced_at: string | null;
  notes: string | null;
}

export interface DriverRow {
  id: string;
  full_name: string;
  phone: string;
  license_number: string | null;
  license_expiry: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface StopRow {
  id: string;
  route_id: string;
  sequence: number;
  name: string;
  address: string | null;
  morning_pickup_time: string | null;
  afternoon_dropoff_time: string | null;
}

export interface RouteRow {
  id: string;
  name: string;
  code: string | null;
  description: string | null;
  vehicle_id: string | null;
  vehicle: VehicleRow | null;
  driver_id: string | null;
  driver: DriverRow | null;
  morning_start_time: string | null;
  afternoon_start_time: string | null;
  is_active: boolean;
  stops: StopRow[];
  student_count: number | null;
}

export interface RosterRow {
  assignment_id: string;
  student_id: string;
  student_code: string;
  first_name: string;
  last_name: string;
  pickup_stop_id: string | null;
  dropoff_stop_id: string | null;
}

export interface TripRow {
  id: string;
  route_id: string;
  route_name: string | null;
  route_code: string | null;
  trip_date: string;
  direction: TripDirection;
  status: TripStatus;
  vehicle_id: string | null;
  vehicle_registration: string | null;
  driver_id: string | null;
  driver_name: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_reason: string | null;
  notes: string | null;
  counts: Partial<Record<BoardingStatus, number>>;
}

export interface BoardingRow {
  id: string;
  trip_id: string;
  student_id: string;
  student_name: string | null;
  student_code: string | null;
  pickup_stop_id: string | null;
  dropoff_stop_id: string | null;
  stop_name: string | null;
  status: BoardingStatus;
  event_at: string | null;
  notes: string | null;
}

export interface TransportDashboard {
  today: string;
  summary: {
    active_routes: number;
    active_vehicles: number;
    active_drivers: number;
    students_on_routes: number;
    trips_in_progress: number;
    trips_completed: number;
    trips_planned: number;
    trips_cancelled: number;
    on_board_now: number;
    issue_count: number;
  };
  in_progress: TripRow[];
  planned: TripRow[];
  completed: TripRow[];
  cancelled: TripRow[];
  issues: Array<{ trip_id: string; type: string; detail: string }>;
}

// ── Hooks ────────────────────────────────────────────────────────────────────

export function useTransportDashboard() {
  return useQuery<TransportDashboard>({
    queryKey: ["transport", "dashboard"],
    queryFn: () => transportApi.dashboard(),
    // Live operational view — refresh while the page is open. 20s is gentle
    // enough to avoid a refetch on every boarding click but tight enough
    // for "current trip" status to feel real.
    refetchInterval: 20_000,
    staleTime: 10_000,
  });
}

export function useVehicles() {
  return useQuery<{ items: VehicleRow[] }>({
    queryKey: ["transport", "vehicles"],
    queryFn: () => transportApi.vehicles.list(),
    staleTime: 30_000,
  });
}

export function useDrivers() {
  return useQuery<{ items: DriverRow[] }>({
    queryKey: ["transport", "drivers"],
    queryFn: () => transportApi.drivers.list(),
    staleTime: 30_000,
  });
}

export function useRoutes(includeStops = false) {
  return useQuery<{ items: RouteRow[] }>({
    queryKey: ["transport", "routes", { includeStops }],
    queryFn: () => transportApi.routes.list({ include_stops: includeStops }),
    staleTime: 30_000,
  });
}

export function useRoute(id: string | null) {
  return useQuery<{ route: RouteRow; roster: RosterRow[] }>({
    queryKey: ["transport", "routes", id],
    queryFn: () => transportApi.routes.get(id!),
    enabled: !!id,
    staleTime: 15_000,
  });
}

export function useTrip(id: string | null) {
  return useQuery<{ trip: TripRow; boardings: BoardingRow[] }>({
    queryKey: ["transport", "trips", id],
    queryFn: () => transportApi.trips.get(id!),
    enabled: !!id,
    // Driver flips boarding states frequently — keep this fresh.
    staleTime: 5_000,
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

function mutate<T extends string>(qkey: T) {
  // Tiny helper to avoid repeating invalidate-all-transport in every mutation.
  return ["transport", qkey] as const;
}

function bumpTransport(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["transport"] });
}

export function useCreateVehicle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => transportApi.vehicles.create(data),
    onSuccess: () => { bumpTransport(qc); toast.success("Vehicle added."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to add vehicle.")),
  });
}

export function useUpdateVehicle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => transportApi.vehicles.update(id, data),
    onSuccess: () => { bumpTransport(qc); toast.success("Vehicle updated."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to update vehicle.")),
  });
}

export function useDeleteVehicle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => transportApi.vehicles.remove(id),
    onSuccess: () => { bumpTransport(qc); toast.success("Vehicle removed."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to remove vehicle.")),
  });
}

export function useCreateDriver() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => transportApi.drivers.create(data),
    onSuccess: () => { bumpTransport(qc); toast.success("Driver added."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to add driver.")),
  });
}

export function useUpdateDriver() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => transportApi.drivers.update(id, data),
    onSuccess: () => { bumpTransport(qc); toast.success("Driver updated."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to update driver.")),
  });
}

export function useDeleteDriver() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => transportApi.drivers.remove(id),
    onSuccess: () => { bumpTransport(qc); toast.success("Driver removed."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to remove driver.")),
  });
}

export function useCreateRoute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => transportApi.routes.create(data),
    onSuccess: () => { bumpTransport(qc); toast.success("Route created."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to create route.")),
  });
}

export function useUpdateRoute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => transportApi.routes.update(id, data),
    onSuccess: () => { bumpTransport(qc); toast.success("Route updated."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to update route.")),
  });
}

export function useDeleteRoute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => transportApi.routes.remove(id),
    onSuccess: () => { bumpTransport(qc); toast.success("Route removed."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to remove route.")),
  });
}

export function useAddStop(routeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => transportApi.routes.addStop(routeId, data),
    onSuccess: () => { bumpTransport(qc); toast.success("Stop added."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to add stop.")),
  });
}

export function useUpdateStop() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => transportApi.routes.updateStop(id, data),
    onSuccess: () => { bumpTransport(qc); toast.success("Stop updated."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to update stop.")),
  });
}

export function useDeleteStop() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => transportApi.routes.removeStop(id),
    onSuccess: () => { bumpTransport(qc); toast.success("Stop removed."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to remove stop.")),
  });
}

export function useAssignStudent(routeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { student_id: string; pickup_stop_id?: string; dropoff_stop_id?: string }) =>
      transportApi.routes.assignStudent(routeId, data),
    onSuccess: () => { bumpTransport(qc); toast.success("Student assigned."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to assign student.")),
  });
}

export function useUnassignStudent(routeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (student_id: string) => transportApi.routes.unassignStudent(routeId, student_id),
    onSuccess: () => { bumpTransport(qc); toast.success("Student removed."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to remove student.")),
  });
}

export function useCreateTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { route_id: string; direction: "morning" | "afternoon"; trip_date?: string }) =>
      transportApi.trips.create(data),
    onSuccess: () => { bumpTransport(qc); toast.success("Trip created."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to create trip.")),
  });
}

export function useStartTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => transportApi.trips.start(id),
    onSuccess: () => { bumpTransport(qc); toast.success("Trip started."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to start trip.")),
  });
}

export function useCompleteTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => transportApi.trips.complete(id),
    onSuccess: () => { bumpTransport(qc); toast.success("Trip completed."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to complete trip.")),
  });
}

export function useCancelTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      transportApi.trips.cancel(id, reason),
    onSuccess: () => { bumpTransport(qc); toast.success("Trip cancelled."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to cancel trip.")),
  });
}

export function useMarkBoarding(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { student_id: string; status: BoardingStatus; notes?: string }) =>
      transportApi.trips.board(tripId, data),
    onSuccess: () => { bumpTransport(qc); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to update boarding.")),
  });
}
