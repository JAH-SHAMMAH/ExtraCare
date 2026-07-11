"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { facilityApi } from "@/lib/api";
import type {
  FacilityItem, FacilityLookup, FacilityDepartment, FacilityStaffMember,
  FacilityComplaint, FacilityInspection, FacilityMaintenanceItem,
  FacilityApprovalLevel, FacilityRequisition, FacilityReport, FacilityAuditItem,
} from "@/types";

function mut<T>(fn: (v: any) => Promise<T>, keys: string[], ok: string) {
  return () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] })); if (ok) toast.success(ok); },
      onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed."),
    });
  };
}

// Facilities
export function useFacilities() { return useQuery<FacilityItem[]>({ queryKey: ["fac-facilities"], queryFn: () => facilityApi.facilities.list() }); }
export const useSaveFacility = mut((v: { id?: string; data: object }) => (v.id ? facilityApi.facilities.update(v.id, v.data) : facilityApi.facilities.create(v.data)), ["fac-facilities"], "Facility saved.");
export const useDeleteFacility = mut((id: string) => facilityApi.facilities.remove(id), ["fac-facilities"], "Facility deleted.");

// Types / Locations / Departments
export function useFacilityTypes() { return useQuery<FacilityLookup[]>({ queryKey: ["fac-types"], queryFn: () => facilityApi.types.list() }); }
export const useSaveFacilityType = mut((v: { id?: string; data: object }) => (v.id ? facilityApi.types.update(v.id, v.data) : facilityApi.types.create(v.data)), ["fac-types"], "Saved.");
export const useDeleteFacilityType = mut((id: string) => facilityApi.types.remove(id), ["fac-types"], "Deleted.");

export function useFacilityLocations() { return useQuery<FacilityLookup[]>({ queryKey: ["fac-locations"], queryFn: () => facilityApi.locations.list() }); }
export const useSaveFacilityLocation = mut((v: { id?: string; data: object }) => (v.id ? facilityApi.locations.update(v.id, v.data) : facilityApi.locations.create(v.data)), ["fac-locations"], "Saved.");
export const useDeleteFacilityLocation = mut((id: string) => facilityApi.locations.remove(id), ["fac-locations"], "Deleted.");

export function useFacilityDepartments() { return useQuery<FacilityDepartment[]>({ queryKey: ["fac-departments"], queryFn: () => facilityApi.departments.list() }); }
export const useSaveFacilityDepartment = mut((v: { id?: string; data: object }) => (v.id ? facilityApi.departments.update(v.id, v.data) : facilityApi.departments.create(v.data)), ["fac-departments"], "Saved.");
export const useDeleteFacilityDepartment = mut((id: string) => facilityApi.departments.remove(id), ["fac-departments"], "Deleted.");

// Staff pools
export function useFacilityStaff(role_type?: string) { return useQuery<FacilityStaffMember[]>({ queryKey: ["fac-staff", role_type], queryFn: () => facilityApi.staff.list(role_type) }); }
export const useSaveFacilityStaff = mut((d: object) => facilityApi.staff.create(d), ["fac-staff"], "Assigned.");
export const useDeleteFacilityStaff = mut((id: string) => facilityApi.staff.remove(id), ["fac-staff"], "Removed.");

// Complaints
export function useFacilityComplaints(mine?: boolean) { return useQuery<FacilityComplaint[]>({ queryKey: ["fac-complaints", mine], queryFn: () => facilityApi.complaints.list(mine) }); }
export const useSaveComplaint = mut((v: { id?: string; data: object }) => (v.id ? facilityApi.complaints.update(v.id, v.data) : facilityApi.complaints.create(v.data)), ["fac-complaints"], "Complaint saved.");
export const useDeleteComplaint = mut((id: string) => facilityApi.complaints.remove(id), ["fac-complaints"], "Deleted.");

// Inspections
export function useFacilityInspections(mine?: boolean) { return useQuery<FacilityInspection[]>({ queryKey: ["fac-inspections", mine], queryFn: () => facilityApi.inspections.list(mine) }); }
export const useSaveInspection = mut((d: object) => facilityApi.inspections.create(d), ["fac-inspections", "fac-complaints"], "Inspection recorded.");
export const useDeleteInspection = mut((id: string) => facilityApi.inspections.remove(id), ["fac-inspections"], "Deleted.");

// Maintenance
export function useFacilityMaintenance(mine?: boolean) { return useQuery<FacilityMaintenanceItem[]>({ queryKey: ["fac-maintenance", mine], queryFn: () => facilityApi.maintenance.list(mine) }); }
export const useSaveMaintenance = mut((v: { id?: string; data: object }) => (v.id ? facilityApi.maintenance.update(v.id, v.data) : facilityApi.maintenance.create(v.data)), ["fac-maintenance"], "Maintenance saved.");

// Approval levels
export function useApprovalLevels() { return useQuery<FacilityApprovalLevel[]>({ queryKey: ["fac-levels"], queryFn: () => facilityApi.approvalLevels.list() }); }
export const useSaveApprovalLevel = mut((v: { id?: string; data: object }) => (v.id ? facilityApi.approvalLevels.update(v.id, v.data) : facilityApi.approvalLevels.create(v.data)), ["fac-levels"], "Saved.");
export const useDeleteApprovalLevel = mut((id: string) => facilityApi.approvalLevels.remove(id), ["fac-levels"], "Deleted.");

// Requisitions
export function useFacilityRequisitions(mine?: boolean) { return useQuery<FacilityRequisition[]>({ queryKey: ["fac-requisitions", mine], queryFn: () => facilityApi.requisitions.list(mine) }); }
export const useCreateRequisition = mut((d: object) => facilityApi.requisitions.create(d), ["fac-requisitions"], "Requisition raised.");
export const useApproveRequisition = mut((id: string) => facilityApi.requisitions.approve(id), ["fac-requisitions"], "Approved.");
export const useDisburseRequisition = mut((id: string) => facilityApi.requisitions.disburse(id), ["fac-requisitions"], "Disbursed.");

// Report / Audit
export function useFacilityReport() { return useQuery<FacilityReport>({ queryKey: ["fac-report"], queryFn: () => facilityApi.report() }); }
export function useFacilityAudit(category?: string) { return useQuery<{ items: FacilityAuditItem[] }>({ queryKey: ["fac-audit", category], queryFn: () => facilityApi.audit(category) }); }
