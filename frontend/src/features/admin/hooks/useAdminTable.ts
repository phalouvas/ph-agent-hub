// =============================================================================
// PH Agent Hub — useAdminTable Hook
// =============================================================================
// Manages pagination, sorting, and filtering state for admin list views.
// Wraps TanStack Query's useQuery and Ant Design Table's onChange handler.
// =============================================================================

import { useState, useCallback } from "react";
import { useQuery, type QueryKey } from "@tanstack/react-query";
import type { PaginatedResponse, ListParams } from "../services/admin";
import type { TablePaginationConfig } from "antd";
import type { SorterResult } from "antd/es/table/interface";

export type { PaginatedResponse, ListParams };

export function useAdminTable<T>(
  queryKey: string[],
  fetcher: (params: ListParams) => Promise<PaginatedResponse<T>>,
  initialParams: Partial<ListParams> = {},
) {
  const [params, setParams] = useState<ListParams>({
    page: 1,
    page_size: 25,
    ...initialParams,
  });

  const { data, isLoading, isFetching } = useQuery({
    queryKey: [...queryKey, params] as QueryKey,
    queryFn: () => fetcher(params),
  });

  const updateParams = useCallback((patch: Partial<ListParams>) => {
    setParams((prev) => ({ ...prev, ...patch }));
  }, []);

  const handleTableChange = useCallback(
    (
      pagination: TablePaginationConfig,
      _filters: Record<string, unknown>,
      sorter: SorterResult<T> | SorterResult<T>[],
    ) => {
      const s = Array.isArray(sorter) ? sorter[0] : sorter;
      setParams((prev) => ({
        ...prev,
        page: pagination.current ?? 1,
        page_size: pagination.pageSize ?? prev.page_size,
        sort_by: (s.field as string) ?? prev.sort_by,
        sort_dir:
          s.order === "ascend"
            ? "asc"
            : s.order === "descend"
              ? "desc"
              : undefined,
      }));
    },
    [],
  );

  const resetFilters = useCallback(() => {
    setParams({ page: 1, page_size: params.page_size });
  }, [params.page_size]);

  return {
    data,
    isLoading: isLoading || isFetching,
    params,
    updateParams,
    handleTableChange,
    resetFilters,
  };
}
