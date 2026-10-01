import React from 'react';
import {QueryClient, QueryClientProvider, useQuery} from '@tanstack/react-query';
import {ReactQueryDevtools} from '@tanstack/react-query-devtools';
export function CurrentTime({api}) {
  const query=useQuery({queryKey:[api],queryFn:async()=>{
    const response=await fetch(api);
    if(!response.ok) throw new Error(`API unavailable (${response.status})`);
    return response.json();
  }});
  if(query.isPending)return <p>Loading {api}... </p>;
  if(query.error)return <p role="alert">An error has occurred: {query.error.message}</p>;
  return <section><p>---</p><p>API: {query.data.api}</p><p>Time from DB: {query.data.now}</p>{query.isFetching&&<div>Updating...</div>}</section>;
}
const client=new QueryClient();
export function App(){return <QueryClientProvider client={client}><h1>Hey Team! 👋</h1><CurrentTime api="/api/golang/"/><CurrentTime api="/api/node/"/><ReactQueryDevtools initialIsOpen={false}/></QueryClientProvider>}
