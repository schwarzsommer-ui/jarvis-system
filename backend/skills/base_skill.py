class Skill:
    name = "base"
    def install(self): return {"status": "ready"}
    def setup(self): return {"status": "ready"}
    def run(self, payload=None): return {"status": "simulated", "payload": payload or {}}
    def test(self): return True
    def improve(self): return {"status": "planned"}
    def docs(self): return self.__class__.__doc__ or ""
    def live_update(self): return {"skill": self.name, "status": "live"}
