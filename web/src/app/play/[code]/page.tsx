import { Suspense } from "react";
import { Placeholder } from "@/components/placeholder";

/** Phone: join → deck → my results. */
export default function PlayPage(props: PageProps<"/play/[code]">) {
  return (
    <Suspense fallback={<Placeholder title="Play" tasks="3.7, 4.5, 7.3" />}>
      <PlayRoom params={props.params} />
    </Suspense>
  );
}

async function PlayRoom({ params }: { params: PageProps<"/play/[code]">["params"] }) {
  const { code } = await params;
  return (
    <Placeholder title="Play" detail={`Room ${code}: join, deck, results`} tasks="3.7, 4.5, 7.3" />
  );
}
