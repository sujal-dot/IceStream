import { useState, useEffect, useCallback, useRef } from 'react';
import {
  IncidentItem,
  MetricsResponse,
  PipelineStatusResponse,
  QualityResponse,
  SchemaDriftResponse,
  SystemHealthResponse,
} from '../types/dashboard';
import { ApiLineageResponse } from '../types/lineage';
import { MetricsApiService } from '../services/metricsApi';
import { PipelineApiService } from '../services/pipelineApi';
import { LineageApiService } from '../services/lineageApi';
import { IncidentsApiService } from '../services/incidentsApi';
import { QualityApiService } from '../services/qualityApi';
import { SchemaApiService } from '../services/schemaApi';

export interface UseDashboardDataReturn {
  metrics: MetricsResponse | null;
  pipelineStatus: PipelineStatusResponse | null;
  lineage: ApiLineageResponse | null;
  incidents: IncidentItem[];
  quality: QualityResponse | null;
  systemHealth: SystemHealthResponse | null;
  schemaDrift: SchemaDriftResponse | null;
  isLoading: boolean;
  isRefreshing: boolean;
  errors: {
    metrics?: string;
    pipeline?: string;
    lineage?: string;
    incidents?: string;
    quality?: string;
    systemHealth?: string;
    schemaDrift?: string;
  };
  lastUpdated: string | null;
  refreshData: (manual?: boolean) => Promise<void>;
}

export const useDashboardData = (pollIntervalMs: number = 2000): UseDashboardDataReturn => {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [lineage, setLineage] = useState<ApiLineageResponse | null>(null);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [quality, setQuality] = useState<QualityResponse | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null);
  const [schemaDrift, setSchemaDrift] = useState<SchemaDriftResponse | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [errors, setErrors] = useState<{
    metrics?: string;
    pipeline?: string;
    lineage?: string;
    incidents?: string;
    quality?: string;
    systemHealth?: string;
    schemaDrift?: string;
  }>({});
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const isMountedRef = useRef<boolean>(true);

  const fetchAllData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    }

    const newErrors: typeof errors = {};

    const [
      statusResult,
      metricsResult,
      lineageResult,
      incidentsResult,
      qualityResult,
      healthResult,
      driftResult,
    ] = await Promise.allSettled([
      PipelineApiService.getStatus?.() ?? Promise.reject(new Error('Pipeline status API error')),
      MetricsApiService.getMetrics?.() ?? Promise.reject(new Error('Metrics API error')),
      LineageApiService.getLineage?.() ?? Promise.reject(new Error('Lineage API error')),
      IncidentsApiService.getIncidents?.() ?? Promise.reject(new Error('Incidents API error')),
      QualityApiService.getQuality?.() ?? Promise.reject(new Error('Quality API error')),
      MetricsApiService.getSystemHealth?.() ?? Promise.reject(new Error('System health API error')),
      SchemaApiService.getSchemaDrift?.() ?? Promise.reject(new Error('Schema drift API error')),
    ]);

    if (!isMountedRef.current) return;

    if (statusResult.status === 'fulfilled') {
      setPipelineStatus(statusResult.value);
    } else {
      newErrors.pipeline = statusResult.reason?.message || 'Pipeline status API error';
    }

    if (metricsResult.status === 'fulfilled') {
      setMetrics(metricsResult.value);
    } else {
      newErrors.metrics = metricsResult.reason?.message || 'Metrics API error';
    }

    if (lineageResult.status === 'fulfilled') {
      setLineage(lineageResult.value);
    } else {
      newErrors.lineage = lineageResult.reason?.message || 'Lineage API error';
    }

    if (incidentsResult.status === 'fulfilled') {
      setIncidents(incidentsResult.value?.items || []);
    } else {
      newErrors.incidents = incidentsResult.reason?.message || 'Incidents API error';
    }

    if (qualityResult.status === 'fulfilled') {
      setQuality(qualityResult.value);
    } else {
      newErrors.quality = qualityResult.reason?.message || 'Quality API error';
    }

    if (healthResult.status === 'fulfilled') {
      setSystemHealth(healthResult.value);
    } else {
      newErrors.systemHealth = healthResult.reason?.message || 'System health API error';
    }

    if (driftResult.status === 'fulfilled') {
      setSchemaDrift(driftResult.value);
    } else {
      newErrors.schemaDrift = driftResult.reason?.message || 'Schema drift API error';
    }

    setErrors(newErrors);
    setLastUpdated(new Date().toLocaleTimeString());
    setIsLoading(false);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    if (pollIntervalMs <= 0) {
      setIsLoading(false);
      return;
    }

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
    systemHealth,
    schemaDrift,
    isLoading,
    isRefreshing,
    errors,
    lastUpdated,
    refreshData: (manual = true) => fetchAllData(manual),
  };
};
