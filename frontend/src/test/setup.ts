import '@testing-library/jest-dom';

// Mock ResizeObserver for React Flow compatibility in jsdom tests
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
