import { Suspense } from "react";
import { Placeholder } from "@/components/placeholder";

/** Host big screen: lobby → progress → reveal. */
export default function HostPage(props: PageProps<"/host/[code]">) {
  return (
    <Suspense fallback={<Placeholder title="Host screen" tasks="3.6, 4.8, 7.2" />}>
      <HostRoom params={props.params} />
    </Suspense>
  );
}

async function HostRoom({ params }: { params: PageProps<"/host/[code]">["params"] }) {
  const { code } = await params;
  return (
    <Placeholder
      title="Host screen"
      detail={`Room ${code}: lobby, progress, reveal`}
      tasks="3.6, 4.8, 7.2"
    />
  );
}
