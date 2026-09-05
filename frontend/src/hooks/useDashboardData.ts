import { useState, useEffect, useCallback, useRef } from 'react';
import {
  IncidentItem,
  MetricsResponse,
  PipelineStatusResponse,
  QualityResponse,
} from '../types/dashboard';
import { ApiLineageResponse } from '../types/lineage';
import { MetricsApiService } from '../services/metricsApi';
import { PipelineApiService } from '../services/pipelineApi';
import { LineageApiService } from '../services/lineageApi';
import { IncidentsApiService } from '../services/incidentsApi';
import { QualityApiService } from '../services/qualityApi';

export interface UseDashboardDataReturn {
  metrics: MetricsResponse | null;
  pipelineStatus: PipelineStatusResponse | null;
  lineage: ApiLineageResponse | null;
  incidents: IncidentItem[];
  quality: QualityResponse | null;
  isLoading: boolean;
  isRefreshing: boolean;
  errors: {
    metrics?: string;
    pipeline?: string;
    lineage?: string;
    incidents?: string;
    quality?: string;
  };
  lastUpdated: string | null;
  refreshData: (manual?: boolean) => Promise<void>;
}

export const useDashboardData = (pollIntervalMs: number = 15000): UseDashboardDataReturn => {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [lineage, setLineage] = useState<ApiLineageResponse | null>(null);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [quality, setQuality] = useState<QualityResponse | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [errors, setErrors] = useState<{
    metrics?: string;
    pipeline?: string;
    lineage?: string;
    incidents?: string;
    quality?: string;
  }>({});
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const isMountedRef = useRef<boolean>(true);

  const fetchAllData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    }

    const newErrors: typeof errors = {};

    // 1. Fetch Pipeline Status
    try {
      const statusRes = await PipelineApiService.getStatus();
      if (isMountedRef.current) setPipelineStatus(statusRes);
    } catch (err: any) {
      newErrors.pipeline = err.message || 'Pipeline status API error';
    }

    // 2. Fetch Metrics
    try {
      const metricsRes = await MetricsApiService.getMetrics();
      if (isMountedRef.current) setMetrics(metricsRes);
    } catch (err: any) {
      newErrors.metrics = err.message || 'Metrics API error';
    }

    // 3. Fetch Lineage
    try {
      const lineageRes = await LineageApiService.getLineage();
      if (isMountedRef.current) setLineage(lineageRes);
    } catch (err: any) {
      newErrors.lineage = err.message || 'Lineage API error';
    }

    // 4. Fetch Incidents
    try {
      const incidentsRes = await IncidentsApiService.getIncidents();
      if (isMountedRef.current) setIncidents(incidentsRes.items || []);
    } catch (err: any) {
      newErrors.incidents = err.message || 'Incidents API error';
    }

    // 5. Fetch Quality
    try {
      const qualityRes = await QualityApiService.getQuality();
      if (isMountedRef.current) setQuality(qualityRes);
    } catch (err: any) {
      newErrors.quality = err.message || 'Quality API error';
    }

    if (isMountedRef.current) {
      setErrors(newErrors);
      setLastUpdated(new Date().toLocaleTimeString());
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    fetchAllData(false);

    const intervalId = setInterval(() => {
      fetchAllData(false);
    }, pollIntervalMs);

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [fetchAllData, pollIntervalMs]);

  return {
    metrics,
    pipelineStatus,
    lineage,
    incidents,
    quality,
    isLoading,
    isRefreshing,
    errors,
    lastUpdated,
    refreshData: (manual = true) => fetchAllData(manual),
  };
};
