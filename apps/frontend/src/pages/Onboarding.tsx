import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { ErrorNotice } from "../components/ErrorNotice";
import { Page } from "../components/Page";
import { useMe, useSetMe } from "../features/auth/session";
import { GoalForm, type GoalValues } from "../features/profile/GoalForm";

export function Onboarding() {
  const me = useMe();
  const setMe = useSetMe();
  const navigate = useNavigate();
  const save = useMutation({
    mutationFn: (values: GoalValues) =>
      unwrap(api.PATCH("/api/v1/me", { body: { ...values, onboarded: true } })),
    onSuccess: (data) => {
      setMe(data);
      navigate("/inicio", { replace: true });
    },
  });
  if (!me.data) return null;
  return (
    <Page title="Cuéntanos tu meta">
      <p>Con esto ajustamos lo que te mostramos. Puedes cambiarlo después en "Perfil".</p>
      <ErrorNotice error={save.error} />
      <GoalForm me={me.data} submitLabel="Guardar y continuar" busy={save.isPending} onSubmit={(v) => save.mutate(v)} />
    </Page>
  );
}
