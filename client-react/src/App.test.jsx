// @vitest-environment jsdom
import React from 'react';
import {test,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {CurrentTime} from './App.jsx';
test('displays database response and provider failures',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({api:'golang',now:'2026-01-01'})}));
  const view=render(<QueryClientProvider client={new QueryClient()}><CurrentTime api="/api/golang/"/></QueryClientProvider>);
  expect(await screen.findByText('Time from DB: 2026-01-01')).toBeTruthy();view.unmount();
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:503}));
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><CurrentTime api="/bad"/></QueryClientProvider>);
  expect((await screen.findByRole('alert')).textContent).toContain('503');vi.unstubAllGlobals();
});
